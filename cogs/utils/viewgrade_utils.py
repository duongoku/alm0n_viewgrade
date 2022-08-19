from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
from pdf2image import convert_from_path
from platform import python_compiler
from scipy import ndimage
import cv2
import numpy as np
import os
import re
import requests


def clear_temporary():
    temp_dir = os.getenv('TEMPDIR')
    files = os.listdir('temp')
    for file in files:
        os.remove(f'{temp_dir}/{file}')
    return True


def minimum_x(text_annotation):
    vertices = text_annotation.bounding_poly.vertices
    min_y = vertices[0].y
    for vertex in vertices:
        if vertex.y < min_y:
            min_y = vertex.y
    return min_y


def minimum_y(text_annotation):
    vertices = text_annotation.bounding_poly.vertices
    min_x = vertices[0].x
    for vertex in vertices:
        if vertex.x < min_x:
            min_x = vertex.x
    return min_x


def sort_key(text_annotation):
    min_x = minimum_x(text_annotation)
    min_y = minimum_y(text_annotation)
    return (min_x, min_y)


def get_text(filepath, crop):
    credentials = service_account.Credentials.from_service_account_file(
        os.getenv('VISION_CREDENTIALS')
    )
    client = vision.ImageAnnotatorClient(
        credentials=credentials
    )

    temp_dir = os.getenv('TEMPDIR')
    temppath = f'{temp_dir}/temp_{filepath[len(temp_dir)+1:-4]}.jpg'
    content = None

    if crop:
        image = Image.open(filepath)
        (width, height) = image.size
        image = image.crop((7*width/10, 0, width, height))
        image.save(temppath)
    else:
        temppath = filepath
        # image = Image.open(filepath)
        # (width, height) = image.size
        # image = image.crop((0, 0, width, height/2))
        # image.save(temppath)

    with open(temppath, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    response = client.text_detection(image=image)  # pylint: disable=no-member

    text = response.text_annotations[0].description

    # If crop is true (meaning only need to get scores),
    # we need to sort the repsonses by their x and y coordinates
    if crop:
        tmp = response.text_annotations[1:]
        tmp.sort(key=sort_key)
        text = '\n'.join(list(map(lambda x: x.description, tmp)))

    with open(f'{temp_dir}/text_{filepath[len(temp_dir)+1:-4]}.txt', 'w+', encoding='utf8') as f:
        f.write(text)

    if response.error.message:
        raise Exception(
            f'{response.error.message}\n'
            'For more info on error messages, check: https://cloud.google.com/apis/design/errors'
        )

    return text

# This function is from this stackoverflow answer: https://stackoverflow.com/questions/57964634/python-opencv-skew-correction-for-ocr


def correct_skew(image, delta=1, limit=10):
    # Convert PIL image into cv2 image
    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def determine_score(arr, angle):
        data = ndimage.rotate(arr, angle, reshape=False, order=0)
        histogram = np.sum(data, axis=1, dtype=float)
        score = np.sum((histogram[1:] - histogram[:-1]) ** 2, dtype=float)
        return histogram, score

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    scores = []
    angles = np.arange(-limit, limit + delta, delta)
    for angle in angles:
        histogram, score = determine_score(thresh, angle)
        scores.append(score)

    best_angle = angles[scores.index(max(scores))]

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, best_angle, 1.0)
    corrected = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)

    return corrected


def make_images(filepath, index):
    temp_dir = os.getenv('TEMPDIR')
    images = convert_from_path(filepath)

    for i in range(len(images)):
        images[i] = Image.fromarray(correct_skew(images[i]))
        images[i].save(f'{temp_dir}/page{index}{i}.jpg', 'JPEG')


def get_file(url, filepath):
    try:
        res = requests.get(url, timeout=8)
        with open(filepath, 'wb+') as f:
            f.write(res.content)
    except (OSError, requests.RequestException) as error:
        print(f'Couldn\'t get {url}: {error}')
        return False
    return True


def remove_lines_with_numbers(lines):
    return list(filter(lambda x: not re.search(r'\d', x), lines))


def remove_lines_with_colons(lines):
    return list(filter(lambda x: not re.search(r':', x), lines))


def remove_lines_with_skipwords(lines, skipwords_file='skipwords.txt'):
    # Skipwords are in upper case
    with open(skipwords_file, 'r', encoding='utf8') as f:
        skipwords = f.readlines()
    return list(filter(lambda x: not any(word.strip() in x.upper() for word in skipwords), lines))


def get_lecturer_and_course(filepath):
    lecturer = ''
    course = ''

    lines = get_lines(filepath)
    lines = remove_lines_with_numbers(lines)
    lines = remove_lines_with_skipwords(lines)

    vn = r'[a-záàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệóòỏõọôốồổỗộơớờởỡợíìỉĩịúùủũụưứừửữựýỳỷỹỵđ ]+'

    for i in range(len(lines)):
        if re.fullmatch(vn, lines[i].strip().lower()):
            if len(lines[i].split(' ')) >= 2:
                lecturer = lines[i].strip()
                course = lines[i+1].strip()
                break

    if lecturer == '' or len(lecturer.split(' ')) < 2:
        lecturer = 'Unreadable Name'
    if course == '' or len(course.split(' ')) < 2:
        course = 'Unreadable Course Name'

    return (lecturer, course)


def get_lines(filepath):
    lines = []

    with open(filepath, 'r', encoding='utf8') as f:
        lines = f.readlines()

    for line in lines:
        line = line[:-1]

    return lines


def score_filter(lines):
    rt = []

    for line in lines:
        s = ''
        line = line.replace(',', '.')

        for char in line:
            if (char == '.') or (char >= '0' and char <= '9'):
                s = s + char

        if len(s) > 0 and len(s) < 4 and s != '.' and s.replace('.', '', 1).isdigit():
            if float(s) < 11:
                rt.append(float(s))

    return rt


def strip_to_numeric(txt):
    rt = re.sub(r'[^0-9]', '', txt)
    return int(rt)


def extract_score(filepaths):
    lecturer = 'Unreadable Name'
    course = 'Unreadable Course Name'

    midterm_mul = 0.3
    final_mul = 1 - midterm_mul

    scores = []

    temp_dir = os.getenv('TEMPDIR')

    get_text(filepaths[0], False)
    lecturer, course = get_lecturer_and_course(
        f'{temp_dir}/text_{filepaths[0][len(temp_dir)+1:-4]}.txt'
    )

    print(f"{filepaths} -> {(lecturer, midterm_mul, final_mul)}")

    extracted = 0
    total = 0

    # return (1, 1, 1, 1, 1)

    for filepath in filepaths:
        get_text(filepath, True)
        lines = get_lines(
            f'{temp_dir}/text_{filepath[len(temp_dir)+1:-4]}.txt'
        )
        lines = score_filter(lines)

        i = 0
        total += len(lines)

        # Ignore the first two lines (midterm and final coefficients)
        if len(lines) > 2:
            if len(lines) % 3 != 0 and lines[0] + lines[1] == 1:
                i = 2
                total -= 2
        # print(f"Total: {total}")

        i += 2
        while i < len(lines):
            if round(midterm_mul*lines[i-2] + final_mul*lines[i-1], 1) == lines[i]:
                scores.append(lines[i])
                i = i + 3
            elif round(midterm_mul*lines[i-1] + final_mul*lines[i-2], 1) == lines[i]:
                scores.append(lines[i])
                i = i + 3
            elif round(midterm_mul*lines[i] + final_mul*lines[i-2], 1) == lines[i-1]:
                scores.append(lines[i-1])
                i = i + 3
            elif round(midterm_mul*lines[i-2] + final_mul*lines[i], 1) == lines[i-1]:
                scores.append(lines[i-1])
                i = i + 3
            elif round(midterm_mul*lines[i] + final_mul*lines[i-1], 1) == lines[i-2]:
                scores.append(lines[i-2])
                i = i + 3
            elif round(midterm_mul*lines[i-1] + final_mul*lines[i], 1) == lines[i-2]:
                scores.append(lines[i-2])
                i = i + 3
            else:
                i = i + 1

    extracted = len(scores)
    total = total/3

    return (lecturer, course, scores, extracted, total)


def classify_scores(scores):
    rt = {
        'A+': 0,
        'A ': 0,
        'B+': 0,
        'B ': 0,
        'C+': 0,
        'C ': 0,
        'D+': 0,
        'D ': 0,
        'F ': 0,
    }

    for score in scores:
        if score >= 9.0:
            rt['A+'] = rt['A+'] + 1
        elif score >= 8.5:
            rt['A '] = rt['A '] + 1
        elif score >= 8.0:
            rt['B+'] = rt['B+'] + 1
        elif score >= 7.0:
            rt['B '] = rt['B '] + 1
        elif score >= 6.5:
            rt['C+'] = rt['C+'] + 1
        elif score >= 5.5:
            rt['C '] = rt['C '] + 1
        elif score >= 5.0:
            rt['D+'] = rt['D+'] + 1
        elif score >= 4.0:
            rt['D '] = rt['D '] + 1
        else:
            rt['F '] = rt['F '] + 1

    return rt


if __name__ == '__main__':
    import dotenv
    dotenv.load_dotenv()

    temp_dir = os.getenv('TEMPDIR')

    # lecturer = get_lecturer(f'{temp_dir}/text.txt')
    # print(lecturer)

    # lmao = get_lines(f'{temp_dir}/text.txt')
    # lmao = score_filter(lmao)
    # print(lmao)

    # make_images(f'{temp_dir}/6.pdf', 99)
    # txt = get_text(f'{temp_dir}/page990.jpg', True)
    # print(txt)

    # print(get_lecturer_and_course(f'{temp_dir}/text_page00.txt'))

    (lecturer, course, result, extracted, total) = extract_score(
        [f'{temp_dir}/page00.jpg'])
    print(
        f"Lecturer: {lecturer}\nCourse: {course}\n"
        f"{result}\n"
        f"Extracted={extracted}\nTotal~{total}\n"
        f"Coverage={round(extracted/(total)*100, 2)}%"
    )
