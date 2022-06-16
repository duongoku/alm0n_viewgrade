# alm0n_viewgrade

alm0n for UET's viewgrade

## Table of Contents

- [alm0n_viewgrade](#alm0n_viewgrade)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Disclaimer](#disclaimer)

## Prerequisites

-   [Python 3.10+](https://www.python.org/downloads/release/python-3100/)
-   A Google Cloud Vision credential file (see [this guide](https://cloud.google.com/vision/docs/auth))
-   A [viewgrade](http://112.137.129.30/viewgrade/) account

## Installation

-   Clone this repository and create a virtual environment(optional):

```
# Below are the steps to create a virtual environment on Windows
# If you are using other operating systems, some of the steps may be different
git clone https://github.com/duongoku/alm0n_viewgrade.git
cd alm0n_viewgrade
python -m venv venv
venv\Scripts\activate
```

-   Install dependencies:

```
pip install -r requirements.txt
```

-   Create an .env file in the root directory of this repository and fill it with your credentials, see .env-example file for details

## Usage

-   Run the bot:

```
python bot.py
```

-   Invite the bot to your server, an invitation url will be shown in the console after the bot is started
-   Chat `~help` (if you didn't change the command prefix) to see the list of commands

## Disclaimer

-   The accuracy of the bot is not guaranteed (because I used some shabby logic), use at your own risk
