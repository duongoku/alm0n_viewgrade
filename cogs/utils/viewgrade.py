from cogs.utils import viewgrade_utils

import json
import os
import re
import requests
import threading
import time

from matplotlib import pyplot as plt

ROOT = "http://112.137.129.30/viewgrade"
MAX_FILES = 100


def get_session():
    username = os.getenv("VIEWGRADE_USERNAME")
    password = os.getenv("VIEWGRADE_PASSWORD")

    url = f"{ROOT}/submitLoginForm"

    res = requests.get(ROOT)

    cookies = res.cookies
    token = re.findall(r"_token.+?>", res.text)[0][15:-2]

    cookies.set("XSRF-TOKEN", res.cookies["XSRF-TOKEN"])
    cookies.set("laravel_session", res.cookies["laravel_session"])

    data = {
        "_token": token,
        "username": username,
        "password": password,
    }

    res = requests.request(method="POST", url=url, data=data, cookies=cookies)

    cookies = res.cookies

    print(f"Get viewgrade session status code: {res.status_code}")
    # print(f"token: {token}\ncookie: {cookies}\n")

    return (token, cookies)


def get_classes(course_id, edu_type=0, term_id_max=100):
    url = f"{ROOT}/home/getSearchWithTerm"

    (token, cookies) = get_session()

    data = {
        "_token": token,
        "input": course_id,
        "idterm": "0",
        "type_education": edu_type,
    }

    rt = []

    try:
        for i in range(term_id_max + 1):
            data["idterm"] = term_id_max - i

            res = requests.request(
                method="POST", url=url, data=data, cookies=cookies)

            if res.text == "-1":
                continue

            json_text = res.text.replace(
                "\\/", "/").encode().decode("unicode_escape")

            json_obj = json.loads(json_text)

            if isinstance(json_obj, list):
                rt.extend(json_obj[0])
    except requests.RequestException as error:
        print(error)

    return rt


def get_grade_files(course_id, edu_type=0, term_id_max=100):
    classes = get_classes(course_id, edu_type, term_id_max)
    rt = []

    for cl in classes:
        if len(cl[2]) > 0 and cl[3] != None:
            rt.append(f"{ROOT}/{cl[2]}")

    print("Done getting files urls!")

    return rt


def get_terms():
    url = f"{ROOT}/home/getListYearTerm"

    (token, cookies) = get_session()

    data = {
        "_token": token,
    }

    res = requests.request(method="POST", url=url, data=data, cookies=cookies)
    if res.status_code != 200:
        return []

    json_text = res.text.replace("\\/", "/").encode().decode("unicode_escape")
    json_obj = json.loads(json_text)
    return json_obj


def get_and_make_images(file, index):
    temp_dir = os.getenv("TEMPDIR")
    print(f"Getting file #{index} ...")
    if viewgrade_utils.get_file(file, f"{temp_dir}/{index}.pdf"):
        print(f"Making image for file #{index} ...")
        viewgrade_utils.make_images(f"{temp_dir}/{index}.pdf", index)
        print(f" Done with file  #{index}")
        return True
    return False


# check if cached result matches the course_id and was modified in the last 24 hours
# if not, return None
# if yes, return the cached result
def get_cached_result(course_id: str):
    course_id = course_id.lower()
    cache_dir = os.getenv("CACHEDIR")
    cache_file = f"{cache_dir}/{course_id}.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
        if (os.path.getmtime(cache_file) > time.time() - 24 * 60 * 60):
            return cache
    return None


def cache_result(course_id: str, result):
    # Check if result is empty
    if len(result.keys()) == 0:
        return
    course_id = course_id.lower()
    cache_dir = os.getenv("CACHEDIR")
    cache_file = f"{cache_dir}/{course_id}.json"
    with open(cache_file, "w") as f:
        json.dump(result, f)


# edu_type = 0 for undergraduate and 1 for postgraduate
def get_course(course_id, edu_type=0, term_id_max=100):
    # clean temporary folder
    viewgrade_utils.clear_temporary()

    result = get_cached_result(course_id)
    if result is not None:
        print("Cache hit!")
        return result

    temp_dir = os.getenv("TEMPDIR")

    # get files from viewgrade
    files = get_grade_files(course_id, edu_type, term_id_max)
    threads = []
    if len(files) > MAX_FILES:
        files = files[0:MAX_FILES]
    for i in range(len(files)):
        # get_and_make_images(files[i], i)
        thread = threading.Thread(
            target=get_and_make_images,
            args=(
                files[i],
                i,
            ),
            daemon=True,
        )
        threads.append(thread)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # return None

    files = os.listdir("temp")
    files = list(filter(lambda f: ".jpg" in f, files))
    files.sort(key=viewgrade_utils.strip_to_numeric)

    if len(files) == 0:
        return None

    # processing the files
    threads = []
    grouped_filepaths = []
    current = []
    preprocess_results = []
    result = {}

    def get_scores(filepaths):
        preprocess_results.append(viewgrade_utils.extract_score(filepaths))

    if len(files) > 0:
        current.append(f"{temp_dir}/{files[0]}")
    for i in range(1, len(files)):
        file = files[i]
        if file[4] == current[0][5 + len(temp_dir)]:
            current.append(f"{temp_dir}/{file}")
        else:
            if len(current) > 0:
                grouped_filepaths.append(current)
            current = [f"{temp_dir}/{file}"]
    grouped_filepaths.append(current)

    for filepaths in grouped_filepaths:
        thread = threading.Thread(
            target=get_scores, args=(filepaths,), daemon=True)
        threads.append(thread)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    for p_result in preprocess_results:
        (lecturer, course, scores, extracted, total) = p_result
        if lecturer not in result:
            result[lecturer] = {
                "course": course,
                "scores": scores,
                "extracted": extracted,
                "total": total,
                "final_scores": {},
            }
        else:
            if course != "Unreadable Course Name":
                result[lecturer]["course"] = course
            result[lecturer]["scores"].extend(scores)
            result[lecturer]["extracted"] = result[lecturer]["extracted"] + extracted
            result[lecturer]["total"] = result[lecturer]["total"] + total

    for lecturer in result:
        result[lecturer]["final_scores"] = viewgrade_utils.classify_scores(
            result[lecturer]["scores"]
        )

    # cache the result
    cache_result(course_id, result)

    return result


def make_plot(course):
    print("Creating plot . . .")

    labels = list(course.keys())
    width = 0.35

    _, ax = plt.subplots()

    grade_list = {
        "A+": [],
        "A ": [],
        "B+": [],
        "B ": [],
        "C+": [],
        "C ": [],
        "D+": [],
        "D ": [],
        "F ": [],
    }

    left = {
        "A+": [],
        "A ": [],
        "B+": [],
        "B ": [],
        "C+": [],
        "C ": [],
        "D+": [],
        "D ": [],
        "F ": [],
    }

    grade_types = list(grade_list.keys())

    left[grade_types[0]] = [0] * len(labels)

    for name in labels:
        ltr = course[name]
        for t in grade_types:
            if ltr["extracted"] > 0:
                p = ltr["final_scores"][t] / ltr["extracted"] * 100
            else:
                p = 0
            grade_list[t].append(p)

    for i in range(len(labels)):
        for j in range(len(grade_types) - 1):
            left[grade_types[j + 1]].append(
                left[grade_types[j]][i] + grade_list[grade_types[j]][i]
            )

    bars = []
    bars_labels = []

    for t in grade_types:
        bars.append(
            ax.barh(labels, grade_list[t], height=0.5, left=left[t], label=t))
        bl = []
        for i in range(len(labels)):
            if grade_list[t][i] < 5:
                bl.append("")
            else:
                bl.append(t)
        bars_labels.append(bl)

    for i, t in enumerate(grade_types):
        ax.bar_label(bars[i], labels=bars_labels[i], label_type="center")

    ax.set_ylabel("Grade percentage (%)")
    ax.set_title("Grade by lecturer")

    plt.savefig(f'{os.getenv("TEMPDIR")}/plot.png', bbox_inches="tight")

    print("Plot saved")

    return True


if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv()

    # get_session()

    # classes = get_classes('INT3121')
    # files = get_grade_files('INT3121')
    courses = get_course("INT3121")

    # print(classes)
    # print(files)
    print(courses)

    # print(get_course('Testing'))

    course = {
        "Nguyễn Thị Ngọc Diệp": {
            "scores": [
                7.2,
                8.0,
                8.6,
                10.0,
                5.1,
                9.2,
                9.1,
                8.2,
                6.2,
                9.7,
                9.3,
                9.6,
                2.4,
                7.6,
                7.6,
                9.1,
                5.8,
                7.6,
                8.1,
                9.1,
                7.1,
                9.8,
                5.3,
                9.0,
                7.6,
                6.6,
                6.6,
                9.7,
                8.1,
                9.8,
                9.0,
                8.1,
                8.1,
                7.4,
                8.1,
                6.6,
                6.6,
                7.6,
                8.1,
                9.1,
                8.1,
                7.6,
                6.8,
                6.8,
                6.8,
                6.8,
                6.2,
                6.8,
                9.8,
                6.2,
                6.8,
                8.1,
                6.8,
                6.2,
                6.2,
                6.2,
                9.8,
                8.1,
            ],
            "extracted": 58,
            "total": 71.0,
            "final_scores": {
                "A+": 16,
                "A ": 1,
                "B+": 11,
                "B ": 9,
                "C+": 11,
                "C ": 7,
                "D+": 2,
                "D ": 0,
                "F ": 1,
            },
        },
        "Nguyễn Thanh Thủy": {
            "scores": [
                8.0,
                0.0,
                9.0,
                0.0,
                8.0,
                8.0,
                8.0,
                8.0,
                0.0,
                7.0,
                7.0,
                8.0,
                8.0,
                9.0,
                8.0,
                8.0,
                7.0,
                8.0,
                8.0,
                8.0,
            ],
            "extracted": 20,
            "total": 22.0,
            "final_scores": {
                "A+": 2,
                "A ": 0,
                "B+": 12,
                "B ": 3,
                "C+": 0,
                "C ": 0,
                "D+": 0,
                "D ": 0,
                "F ": 3,
            },
        },
        "Vũ Thị Hồng Nhạn": {
            "scores": [8.5, 7.0, 6.0, 10.0, 6.0, 6.0, 8.0, 7.0, 7.0],
            "extracted": 9,
            "total": 13.333333333333334,
            "final_scores": {
                "A+": 1,
                "A ": 1,
                "B+": 1,
                "B ": 3,
                "C+": 0,
                "C ": 3,
                "D+": 0,
                "D ": 0,
                "F ": 0,
            },
        },
    }
    make_plot(course)
