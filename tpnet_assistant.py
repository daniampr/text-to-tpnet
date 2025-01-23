from langchain_groq.chat_models import ChatGroq
from openai import OpenAI
import socket
import json
import jsonschema
import streamlit as st


with open('config/model_config.json') as f:
    model_config = json.load(f)

model = 'llama-3.3-70b-versatile'

llm = ChatGroq(
    model=model,
    temperature=0,
    max_tokens=2000,
    max_retries=2,
    api_key=st.secrets['GROQ_API_KEY'],
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def transcribe(audio_file: str) -> str:
    audio_file = open(audio_file, "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="es"
    )
    return transcription.text


def get_tpnet_response(user_prompt: str, device: str) -> str:
    messages = [
        {"role": "system", "content": model_config[f"system_prompt_{device}"]},
        {"role": "user", "content": user_prompt}
    ]
    response = llm.invoke(messages)
    return response.content


def get_struct_tpnet_response(user_prompt: str, device: str) -> dict:
    '''
    Obtains the TP-NET command output from the model, forcing to return a
    response following the TP-NET command structure.
    Parameters:
        user_prompt (str): The user prompt to send to the model.
    Returns:
        dict: The structured output from the model.
    '''
    try:
        structured_output = llm.with_structured_output(model_config["schema"])
        messages = [
            {"role": "system",
             "content": model_config[f"system_prompt_{device}"]
             },
            {"role": "user", "content": user_prompt}
        ]
        st.markdown(device)
        response = structured_output.invoke(messages)
        return response
    except Exception:
        raise ("An error occurred while obtaining the response."
               " Please check if the IP address is correct or try again."
               )


def parse_output(output: dict) -> str:
    '''
    Checks if the output is valid according to the schema and returns the
    formatted TPNET command to send to the device.
    Parameters:
        output (dict): The structured output from the model.
    Returns:
        str: The formatted TPNET command to send to the device.
    '''
    jsonschema.validate(output, model_config["schema"])
    params = ""
    if isinstance(output['params'], str):
        params = output['params']

    elif isinstance(output['params'], list):
        if len(output['params']) > 0:
            if isinstance(output['params'][0], str):
                for param in output['params']:
                    params += f" {param}"

    return f"{output['type']} {output['command']}{params}\n"


# Configure the VIDA device
PORT = 5800  # UDP port 5800
BUFFER_SIZE = 4096  # Buffer size for receiving data

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_tpnet_command(
        command: str, timeout: float = 2.0, refresh=True) -> str:
    """Send a TPnet command to the Ecler device.
    Parameters:
        command (str): The TP-net command to send.

    Returns:
        str: The full response received from the device.
    """
    device_ip = st.session_state.device_ip
    try:
        # Send the command to the device
        sock.sendto(command.encode(), (device_ip, PORT))
        print(f"Sent command: {command}")

        # Receive the response from the device
        response = []
        sock.settimeout(timeout)
        while True:
            try:
                data, addr = sock.recvfrom(4096)  # Buffer size is 4096 bytes
                response.append(data.decode())
            except socket.timeout:
                break

        # Combine the response into a single string
        full_response = "".join(response)
        print(f"Full response received:\n{full_response}")

        # Update the device data
        refresh_device_data() if refresh else None

        return full_response

    except Exception as e:
        print(f"Error: {e}")
        return "An error is raised."


# -------------------------------
# Helper function: parse GET ALL
# -------------------------------


def refresh_device_data():
    print("refreshing device data...")
    response = send_tpnet_command("GET ALL\n", timeout=1, refresh=False)
    parse_device_data(response)


def parse_device_data(data_response: str):
    """
    Parses a multi-line TP-NET response (from GET ALL, etc.)
    and stores each recognized DATA line in st.session_state["device_data"].

    Supports VIDA, HUB, eMIMO, MIMO
    """

    # Ensure we have a device_data dict with all possible keys
    if "device_data" not in st.session_state:
        st.session_state["device_data"] = {
            # Common fields for VIDA or older code
            "olevel": {},
            "omute": {},
            "slevel": {},
            "smute": {},
            "xlevel": {},
            "xmute": {},
            "gmute": {},
            "glevel": {},
            "info": {},
            "power": "",
            "preset": "",

            # Additional fields for HUB / eMIMO / MIMO
            "ilevel": {},          # ILEVEL <Input> <Value>
            "imute": {},           # IMUTE <Input> YES/NO
            "iname": {},           # INAME <Input> <String>
            "ibassgain": {},       # IBASSGAIN <Input> <Value>
            "imidgain": {},        # IMIDGAIN <Input> <Value>
            "itreblegain": {},     # ITREBLEGAIN <Input> <Value>
            "ivu": {},             # IVU <Input> <Value>

            "oname": {},           # ONAME <Output> <String>
            # olevel -> "olevel" above
            # omute -> "omute" above
            "obassgain": {},        # OBASSGAIN <Output> <Value>
            "omidgain": {},         # OMIDGAIN <Output> <Value>
            "otreblegain": {},      # OTREBLEGAIN <Output> <Value>
            "ovu": {},              # OVU <Output> <Value>
            "osourcesel": {},       # OSOURCESEL <Output> <Input>

            "genvol": None,         # OGENVOL <Value> (HUB only)
            "omutegenvol": None,    # OMUTEGENVOL YES/NO (HUB only)

            "gpi": {},              # GPI <Input> <Value>
            "gpo": {},              # GPO <Output> <Value>
            "virtual_control": {},  # VIRTUAL_CONTROL <Control> <Value>
        }

    lines = data_response.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line.startswith("DATA"):
            continue

        parts = line.split(maxsplit=2)  # e.g. ["DATA","OLEVEL","1 35"]
        if len(parts) < 2:
            continue

        tag = parts[1]       # e.g. "OLEVEL", "ILEVEL", "INAME"
        rest = parts[2] if len(parts) >= 3 else ""

        # Split the remainder to handle parameters
        tokens = rest.split()

        # ------------------------------------------------------------
        #  Existing VIDA fields first (SLEVEL, OLEVEL, SMUTE, etc.)
        # ------------------------------------------------------------
        if tag == "OLEVEL":
            # OLEVEL <channel> <value>
            if len(tokens) >= 2:
                ch, level_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["olevel"][ch] = float(level_str)
                except ValueError:
                    pass

        elif tag == "SLEVEL":
            # SLEVEL <source> <value>
            if len(tokens) >= 2:
                src, level_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["slevel"][src] = float(level_str)
                except ValueError:
                    pass

        elif tag == "OMUTE":
            # OMUTE <channel> YES/NO
            if len(tokens) >= 2:
                ch, status = tokens[0], tokens[1]
                st.session_state["device_data"]["omute"][ch] = status

        elif tag == "SMUTE":
            # SMUTE <source> YES/NO
            if len(tokens) >= 2:
                src, status = tokens[0], tokens[1]
                st.session_state["device_data"]["smute"][src] = status

        elif tag == "XLEVEL":
            # XLEVEL <source> <out_ch> <value>
            if len(tokens) >= 3:
                src, out_ch, level_str = tokens[0], tokens[1], tokens[2]
                try:
                    st.session_state[
                        "device_data"]["xlevel"][(src, out_ch)] = float(
                            level_str)
                except ValueError:
                    pass

        elif tag == "XMUTE":
            # XMUTE <source> <out_ch> YES/NO
            if len(tokens) >= 3:
                src, out_ch, status = tokens[0], tokens[1], tokens[2]
                st.session_state[
                    "device_data"]["xmute"][(src, out_ch)] = status

        elif tag == "GMUTE":
            # GMUTE <Loc/Net/Gen> <groupNum?> YES/NO
            if len(tokens) == 2:
                group_type, status = tokens
                st.session_state[
                    "device_data"]["gmute"][(group_type,)] = status
            elif len(tokens) == 3:
                group_type, group_id, status = tokens
                st.session_state[
                    "device_data"]["gmute"][(group_type, group_id)] = status

        elif tag == "GLEVEL":
            # GLEVEL <Loc/Net/Gen> <groupNum?> <level>
            if len(tokens) == 2:
                group_type, level_str = tokens
                try:
                    st.session_state[
                        "device_data"
                    ]["glevel"][(group_type,)] = float(level_str)
                except ValueError:
                    pass
            elif len(tokens) == 3:
                group_type, group_id, level_str = tokens
                try:
                    st.session_state[
                        "device_data"
                    ]["glevel"][(group_type, group_id)] = float(level_str)
                except ValueError:
                    pass

        elif tag == "POWER":
            # POWER RUNNING/SLEEPING
            st.session_state["device_data"]["power"] = rest

        elif tag == "PRESET":
            # PRESET "User Preset 02"
            st.session_state["device_data"]["preset"] = rest.strip()

        elif tag == "INFO_NAME":
            st.session_state[
                "device_data"]["info"]["name"] = rest.strip().strip('"')

        elif tag == "INFO_MODEL":
            st.session_state["device_data"]["info"]["model"] = rest.strip()

        elif tag == "INFO_VERSION":
            st.session_state["device_data"]["info"]["version"] = rest.strip()

        elif tag == "INFO_MAC":
            # INFO_MAC <NET1/NET2/..> <MAC>
            net_tokens = rest.split()
            if len(net_tokens) >= 2:
                net_interface, mac_addr = net_tokens[0], net_tokens[1]
                if "mac" not in st.session_state["device_data"]["info"]:
                    st.session_state["device_data"]["info"]["mac"] = {}
                st.session_state[
                    "device_data"]["info"]["mac"][net_interface] = mac_addr

        elif tag == "IP_CONFIG":
            # IP_CONFIG <NET1/NET2> <IP> <Netmask> <Gateway>
            net_tokens = rest.split()
            if len(net_tokens) >= 4:
                net_interface = net_tokens[0]
                ip_addr = net_tokens[1]
                netmask = net_tokens[2]
                gateway = net_tokens[3]
                if "ip_config" not in st.session_state["device_data"]["info"]:
                    st.session_state["device_data"]["info"]["ip_config"] = {}
                st.session_state[
                    "device_data"]["info"]["ip_config"][net_interface] = {
                    "ip": ip_addr,
                    "netmask": netmask,
                    "gateway": gateway
                }

        # ------------------------------------------------------------
        #  New fields for HUB / eMIMO / MIMO
        # ------------------------------------------------------------
        elif tag == "ILEVEL":
            # ILEVEL <Input Channel> <Level>
            if len(tokens) >= 2:
                ch, level_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["ilevel"][ch] = float(level_str)
                except ValueError:
                    pass

        elif tag == "IMUTE":
            # IMUTE <Input Channel> YES/NO
            if len(tokens) >= 2:
                ch, status = tokens[0], tokens[1]
                st.session_state["device_data"]["imute"][ch] = status

        elif tag == "INAME":
            if len(tokens) >= 1:
                ch = tokens[0]
                label = rest[len(ch):].strip()
                st.session_state["device_data"]["iname"][ch] = label.strip('"')

        elif tag == "IBASSGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["ibassgain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "IMIDGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["imidgain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "ITREBLEGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["itreblegain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "IVU":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state["device_data"]["ivu"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "ONAME":
            if len(tokens) >= 1:
                ch = tokens[0]
                label = rest[len(ch):].strip()
                st.session_state["device_data"]["oname"][ch] = label.strip('"')

        elif tag == "OBASSGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["obassgain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "OMIDGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["omidgain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "OTREBLEGAIN":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"]["otreblegain"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "OVU":
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                try:
                    st.session_state["device_data"]["ovu"][ch] = float(val_str)
                except ValueError:
                    pass

        elif tag == "OSOURCESEL":
            if len(tokens) >= 2:
                ch, input_sel = tokens[0], tokens[1]
                st.session_state["device_data"]["osourcesel"][ch] = input_sel

        elif tag == "OGENVOL":
            # OGENVOL <Value>
            val_str = tokens[0] if tokens else None
            if val_str:
                try:
                    st.session_state["device_data"]["genvol"] = float(val_str)
                except ValueError:
                    pass

        elif tag == "OMUTEGENVOL":
            # OMUTEGENVOL YES/NO
            if len(tokens) >= 1:
                st.session_state["device_data"]["omutegenvol"] = tokens[0]

        elif tag == "GPI":
            # GPI <Input> <Value>
            if len(tokens) >= 2:
                ch, val_str = tokens[0], tokens[1]
                st.session_state["device_data"]["gpi"][ch] = val_str

        elif tag == "GPO":
            # GPO <Output> <Value>
            if len(tokens) >= 2:
                out_ch, val_str = tokens[0], tokens[1]
                st.session_state["device_data"]["gpo"][out_ch] = val_str

        elif tag == "VIRTUAL_CONTROL":
            # VIRTUAL_CONTROL <ControlID> <Value>
            if len(tokens) >= 2:
                ctrl_id, val_str = tokens[0], tokens[1]
                try:
                    st.session_state[
                        "device_data"
                        ]["virtual_control"][ctrl_id] = float(val_str)
                except ValueError:
                    st.session_state[
                        "device_data"]["virtual_control"][ctrl_id] = val_str
        # ------------------------------------------------------------
        # End of new fields
        # ------------------------------------------------------------
