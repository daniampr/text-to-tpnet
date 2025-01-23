import streamlit as st
from audio_recorder_streamlit import audio_recorder
from streamlit_extras.bottom_container import bottom
from tpnet_assistant import (
    get_struct_tpnet_response,
    parse_output,
    transcribe,
    send_tpnet_command,
    parse_device_data,
    refresh_device_data
)
import os

voice_input = False


st.title("Text-to-TPNET Assistant 🤖")
with st.expander("ℹ️ Disclaimer"):
    st.caption(
        """
        We appreciate your engagement! This model provides a TP-NET command
        based on your text or speech input.Please note, this is a demo version
        and may have limitations based on usage, and TP-NET commands generated
        may not be accurate or complete. Please verify the output you get.
        """
    )

# 1) IP and Connect
device_ip = st.text_input("Enter the IP address of the TPNET device")
st.session_state["device_ip"] = device_ip

col_connect, col_refresh = st.columns([2, 1])
connected = False

with col_connect:
    if st.button("Connect to device with TPNET (SYSTEM CONNECT)"):
        print("Connecting to device...")
        with st.spinner("Connecting to device..."):
            response = send_tpnet_command("SYSTEM CONNECT\n")
            parse_device_data(response)
            st.markdown(
                f"**Connected to TPNET Device successfully! IP**: {device_ip}")
            connected = True


with col_refresh:
    if st.button("Refresh Device Data (GET ALL)"):
        refresh_response = refresh_device_data()
        st.success("Device data refreshed and parsed!")
        st.markdown(
            f"**Response from GET ALL**: {refresh_response}"
            f" -- {type(refresh_response)}"
        )


# 2) SIDEBAR Device Controls
st.sidebar.title("Device Controls")

if "device_data" in st.session_state:
    device_data = st.session_state["device_data"]
    # -- Device Info Display --
    st.sidebar.subheader("Device Info")
    info = device_data.get("info", {})
    st.sidebar.write(f"**Name**: {info.get('name','Unknown')}")
    st.sidebar.write(f"**Model**: {info.get('model','Unknown')}")
    st.sidebar.write(f"**Version**: {info.get('version','Unknown')}")
    mac_dict = info.get("mac", {})
    for net_intf, mac_str in mac_dict.items():
        st.sidebar.write(f"**{net_intf} MAC**: {mac_str}")

    ip_config = info.get("ip_config", {})
    for net_intf, ipdata in ip_config.items():
        ip_addr = ipdata["ip"]
        netmask = ipdata["netmask"]
        gateway = ipdata["gateway"]
        st.sidebar.write(
            f"**{net_intf}**: IP={ip_addr} NM={netmask} GW={gateway}")

    st.sidebar.write(f"**Power**: {device_data.get('power','')}")
    st.sidebar.write(f"**Preset**: {device_data.get('preset','')}")

    # -- OLEVEL + OMUTE --
    st.sidebar.subheader("Output Levels (OLEVEL + MUTE)")
    updated_olevels = {}
    updated_omutes = {}
    olevel_dict = device_data.get("olevel", {})
    omute_dict = device_data.get("omute", {})

    for ch, current_level in olevel_dict.items():
        current_mute = omute_dict.get(ch, "NO")

        cols = st.sidebar.columns([3, 1])
        with cols[0]:
            new_level = st.slider(
                f"OLEVEL Ch {ch}",
                min_value=0.0,
                max_value=100.0,
                value=float(current_level),
                step=1.0,
                key=f"olevel_slider_{ch}"
            )
        with cols[1]:
            new_mute_bool = st.checkbox(
                "Mute",
                value=(current_mute == "YES"),
                key=f"omute_checkbox_{ch}"
            )

        updated_olevels[ch] = new_level
        updated_omutes[ch] = new_mute_bool

    # -- SLEVEL + SMUTE --
    st.sidebar.subheader("Source Levels (SLEVEL + MUTE)")
    updated_slevels = {}
    updated_smutes = {}
    slevel_dict = device_data.get("slevel", {})
    smute_dict = device_data.get("smute", {})

    for src, current_level in slevel_dict.items():
        current_mute = smute_dict.get(src, "NO")

        cols = st.sidebar.columns([3, 1])
        with cols[0]:
            new_level = st.slider(
                f"SLEVEL Src {src}",
                min_value=0.0,
                max_value=100.0,
                value=float(current_level),
                step=1.0,
                key=f"slevel_slider_{src}"
            )
        with cols[1]:
            new_mute_bool = st.checkbox(
                "Mute",
                value=(current_mute == "YES"),
                key=f"smute_checkbox_{src}"
            )

        updated_slevels[src] = new_level
        updated_smutes[src] = new_mute_bool

    # -- XLEVEL + XMUTE --
    if "xlevel" in device_data and len(device_data["xlevel"]) > 0:
        st.sidebar.subheader("Matrix Crosspoint (XLEVEL + MUTE)")
        updated_xlevels = {}
        updated_xmutes = {}

        xlevel_dict = device_data["xlevel"]
        xmute_dict = device_data.get("xmute", {})

        for (src, out_ch), current_level in xlevel_dict.items():
            current_mute = xmute_dict.get((src, out_ch), "NO")

            label = f"XLEVEL S{src}→O{out_ch}"
            cols = st.sidebar.columns([3, 1])
            with cols[0]:
                new_level = st.slider(
                    label,
                    min_value=0.0,
                    max_value=100.0,
                    value=float(current_level),
                    step=1.0,
                    key=f"xlevel_slider_{src}_{out_ch}"
                )
            with cols[1]:
                new_mute_bool = st.checkbox(
                    "Mute",
                    value=(current_mute == "YES"),
                    key=f"xmute_checkbox_{src}_{out_ch}"
                )
            updated_xlevels[(src, out_ch)] = new_level
            updated_xmutes[(src, out_ch)] = new_mute_bool
    else:
        updated_xlevels = {}
        updated_xmutes = {}

    # -- Subscribe/Unsubscribe VU --
    st.sidebar.subheader("VU Meter Subscriptions")
    col_sub_all, col_unsub_all = st.sidebar.columns(2)
    with col_sub_all:
        if st.button("Subscribe ALL"):
            send_tpnet_command("SUBSCRIBE ALL\n")
            st.info("Subscribed to all VU-meters.")
    with col_unsub_all:
        if st.button("Unsubscribe ALL"):
            send_tpnet_command("UNSUBSCRIBE ALL\n")
            st.info("Unsubscribed from all VU-meters.")

    # -- Apply Changes Button --
    if st.sidebar.button("Apply Changes"):
        # OLEVEL
        for ch, new_val in updated_olevels.items():
            old_val = device_data["olevel"][ch]
            if old_val != new_val:
                cmd = f"SET OLEVEL {ch} {new_val}\n"
                send_tpnet_command(cmd)
                device_data["olevel"][ch] = new_val

        # OMUTE
        for ch, new_mute_bool in updated_omutes.items():
            old_mute_str = device_data["omute"].get(ch, "NO")
            new_mute_str = "YES" if new_mute_bool else "NO"
            if old_mute_str != new_mute_str:
                cmd = f"SET OMUTE {ch} {new_mute_str}\n"
                send_tpnet_command(cmd)
                device_data["omute"][ch] = new_mute_str

        # SLEVEL
        for src, new_val in updated_slevels.items():
            old_val = device_data["slevel"][src]
            if old_val != new_val:
                cmd = f"SET SLEVEL {src} {new_val}\n"
                send_tpnet_command(cmd)
                device_data["slevel"][src] = new_val

        # SMUTE
        for src, new_mute_bool in updated_smutes.items():
            old_mute_str = device_data["smute"].get(src, "NO")
            new_mute_str = "YES" if new_mute_bool else "NO"
            if old_mute_str != new_mute_str:
                cmd = f"SET SMUTE {src} {new_mute_str}\n"
                send_tpnet_command(cmd)
                device_data["smute"][src] = new_mute_str

        # XLEVEL
        for (src, out_ch), new_val in updated_xlevels.items():
            old_val = device_data["xlevel"][(src, out_ch)]
            if old_val != new_val:
                cmd = f"SET XLEVEL {src} {out_ch} {new_val}\n"
                send_tpnet_command(cmd)
                device_data["xlevel"][(src, out_ch)] = new_val

        # XMUTE
        for (src, out_ch), new_mute_bool in updated_xmutes.items():
            old_mute_str = device_data["xmute"].get((src, out_ch), "NO")
            new_mute_str = "YES" if new_mute_bool else "NO"
            if old_mute_str != new_mute_str:
                cmd = f"SET XMUTE {src} {out_ch} {new_mute_str}\n"
                send_tpnet_command(cmd)
                device_data["xmute"][(src, out_ch)] = new_mute_str

        st.success("Changes applied!")

    device_name = st.session_state["device_data"]["info"]["name"]

    if "VIDA" in device_name:
        device_name = "VIDA"
    elif "eMIMO" in device_name:
        device_name = "eMIMO"
    elif "MIMO" in device_name:
        device_name = "MIMO"
    elif "HUB" in device_name:
        device_name = "HUB"

    # 3) Main Chat Section
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render conversation
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Audio recorder pinned at bottom
    with bottom():
        audio_data = audio_recorder(pause_threshold=1.0, sample_rate=16000)

    # The pinned chat input
    prompt = st.chat_input("Type a message...")

    transcribed_prompt = ""

    if audio_data:
        audio_file_path = "audio.wav"
        with open(audio_file_path, "wb") as f:
            f.write(audio_data)
        st.success("Audio recorded successfully.")

        with st.spinner("Transcribing..."):
            transcribed_text = transcribe(audio_file_path)

        if transcribed_text and transcribed_text.strip():
            transcribed_prompt = transcribed_text.strip()
            voice_input = True
        os.remove(audio_file_path)

    # If there's typed input or voice input
    if prompt or voice_input:
        final_prompt = transcribed_prompt if voice_input else prompt

        # Append user message
        st.session_state.messages.append(
            {"role": "user", "content": final_prompt}
        )
        with st.chat_message("user"):
            st.markdown(final_prompt)

        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    ai_response_dict = get_struct_tpnet_response(
                        final_prompt, device_name
                    )
                    tpnet_input = parse_output(ai_response_dict)
                    tpnet_response = send_tpnet_command(tpnet_input)
                    refresh_device_data()

                    st.markdown(f"**Command Generated**: {tpnet_input}")
                    st.markdown(f"**Response from TPNET**: {tpnet_response}")

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": f"{tpnet_input}\n{tpnet_response}"
                        }
                    )
                    voice_input = False

                except Exception as e:
                    error_message = "An error occurred during your request."
                    st.error(f"{error_message}: {str(e)}")
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_message}
                    )


else:
    st.sidebar.info("No device data yet."
                    "Click 'Refresh Device Data (GET ALL)' after connecting.")
