# text-to-tpnet
Repository for the source code of an AI model that converts natural language to Ecler's TP-NET protocol commands.

![Image](https://github.com/user-attachments/assets/37507d9c-6dfa-42e2-8392-fd08f16a54cb)

## About TP-NET
TP-NET is a protocol developed by Ecler to control their audio devices. It is a text-based protocol that allows users to send commands to the devices. The protocol is based on a set of commands that are sent to the device to control its functionalities, such as volume control, input selection, and power management, among others. The commands are sent in plain text format, making it easy to implement and use.
Available devices that support TP-NET protocol in this project are:
- VIDA series
- HUB series
- MIMO series
More information about the TP-NET protocol can be found in the [official documentation](https://media.ecler.com/1702317974-ecler-tp-net-protocol-en.pdf).

## About the project
This project aims to develop an AI model that converts natural language commands to TP-NET protocol commands. Supports speech or text input and returns the corresponding TP-NET command. The model is built using the `llama-3.3-70b-versatile` LLM from Meta AI, and deployed using Groq cloud and Streamlit for the web UI. 


## Setting a local environment

### 0. Prerequisites

Recommended to have Python 3.12 or higher. If you are using Windows as the operating system, you may download the [Windows Installer (64-bit)](https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe) executable. If you are using macOS, you may download the [macOS 64-bit universal2 installer](https://www.python.org/ftp/python/3.12.6/python-3.12.6-macos11.pkg) version. For other operating systems or specific versions, check out the [release page](https://www.python.org/downloads/release/python-3126/) of the Python version.


**Important**: Make sure to check the box **"Add Python 3.12 to PATH"** during the installation process.


### 1. Clone the repository
Clone our repository to your local machine using the following command:
```bash
git clone https://github.com/daniampr/text-to-tpnet.git
```

### 2. Create a virtual environment
Create a virtual environment in the root directory of the project:
```bash
python -m venv .venv
```
To activate the virtual environment, run:
```bash
source .venv/bin/activate # For MacOS / Linux
.\.venv\Scripts\activate  # For Windows
```

### 3. Install the dependencies
Install the required dependencies using the following command:
```bash
pip install -r requirements.txt
```

### 4. Run the application
To run the application, execute the command:
```bash
streamlit run app.py
```
