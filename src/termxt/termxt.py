import hashlib
import threading
from Crypto.Cipher import AES
import pathlib
from textual import on
import typer
from textual.app import App, ComposeResult
from textual.widgets import Input, Button, Label
from textual.containers import Container, ScrollableContainer
import requests
import websocket
from rich.text import Text
from configparser import ConfigParser
import json
from sys import exit

global CONFIG_FILE, API_URL, WS_URL

CONFIG_FILE = "/.termxt.cfg"
API_URL = "https://federation-michael-aaa-icon.trycloudflare.com"
WS_URL = "ws://federation-michael-aaa-icon.trycloudflare.com/chat"

config = ConfigParser()


def save_config():
    with open(str(pathlib.Path.home()) + CONFIG_FILE, "w") as config_file:
        config.write(config_file)


def get_config():
    config.read(str(pathlib.Path.home()) + CONFIG_FILE)


def decrypt(hex_ct: str, password: str) -> str:
    d = hashlib.sha512(password.encode()).digest()  # 64 bytes
    key, iv = d[:32], d[32:48]
    ct = bytes.fromhex(hex_ct)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    pt_padded = cipher.decrypt(ct)
    pad_len = pt_padded[-1]
    if not 1 <= pad_len <= 16:
        raise ValueError("Invalid padding")
    pt = pt_padded[:-pad_len]
    return pt.decode("utf-8")


class LoginApp(App):
    def compose(self) -> ComposeResult:
        self.username = Input(placeholder="username")
        self.password = Input(placeholder="password")
        self.message = Label()

        yield self.username
        yield self.password
        yield Button("login", variant="primary")
        yield self.message

    @on(Button.Pressed)
    @on(Input.Submitted)
    def submit(self, event):
        if isinstance(event, Input.Submitted) and event.input == self.username:
            return self.password.focus()
        response = requests.post(
            API_URL + "/user/login",
            json={"username": self.username.value, "password": self.password.value},
        )
        data = response.json()
        self.message.content = data["message"]
        self.username.focus()
        if response.status_code == 200:
            config["account"] = data["data"]
            save_config()
            exit(
                "Successfully logged in! Run 'termxt chat' and enter your friend's username to start a chat with them!"
            )


class RegisterApp(App):
    def compose(self) -> ComposeResult:
        self.username = Input(placeholder="username")
        self.password = Input(placeholder="password")
        self.message = Label()

        yield self.username
        yield self.password
        yield Button("register", variant="primary")
        yield self.message

    @on(Button.Pressed)
    @on(Input.Submitted)
    def submit(self, event):
        if isinstance(event, Input.Submitted) and event.input == self.username:
            return self.password.focus()
        response = requests.post(
            API_URL + "/user/register",
            json={"username": self.username.value, "password": self.password.value},
        )
        data = response.json()
        self.message.content = data["message"]
        self.username.focus()
        if response.status_code == 200:
            config["account"] = data["data"]
            save_config()
            exit(
                "Successfully registered and logged in! Run 'termxt chat' and enter your friend's username to start a chat with them!"
            )


class ChatApp(App):
    username_valid = False
    CSS = """
    #input-container {
        width: 100%;
        height: auto;
        align: center bottom;
        layout: grid;
        grid-size: 2 1;
        grid-columns: 20% 80%;
    }

    #message-container {
        height: 92%;
    }

    .message {
        width: 100%;
        padding: 1;
        background: $surface;
        border-bottom: solid $panel;
        height: auto;
        margin: 1;
    }
    
    .sent {
        text-align: right;
        color: #205bc9;
    }
    """

    def compose(self) -> ComposeResult:
        self.messages = ScrollableContainer(id="message-container")
        yield self.messages
        self.error = Label()
        yield self.error
        with Container(id="input-container"):
            self.username = Input(placeholder="To username (press Enter)", id="username")
            self.message = Input(
                placeholder="Type your message here and press Enter...", id="message"
            )
            yield self.username
            yield self.message

    def on_mount(self):
        def on_message(ws, message):
            self.call_from_thread(self.add_message, message)

        def run_ws():
            self.ws = websocket.WebSocketApp(
                WS_URL,
                on_message=on_message,
                on_close=exit
            )
            self.ws.run_forever()

        threading.Thread(target=run_ws, daemon=True).start()

    def add_message(self, message):
        message = json.loads(message)
        if message["to"] == config["account"]["username"]:
            decrypted = decrypt(message["message"], config["account"]["code"])
            self.messages.mount(
                Label(
                    Text.from_markup(f"[bold]{message["from"]}[/bold]\n {decrypted}"),
                    classes="message",
                )
            )
            self.messages.scroll_page_down()

    @on(Input.Submitted)
    def on_send_message(self, event: Input.Submitted):        
        if event.input.id == "username" or event.input.id == "message":
            response = requests.get(
                f"{API_URL}/user/exists?username={self.username.value}"
            )
            if int(response.text):
                self.error.update(f"{self.username.value} is a real person!")
                self.username_valid = True
            else:
                self.error.update(f"{self.username.value} doesn't exist!")
                self.username_valid = False
        if event.input.id == "message" and event.input.value.replace(" ", "") != "" and self.username_valid:
            msg = event.input.value
            event.input.value = ""
            self.ws.send(json.dumps({"from": config["account"]["username"], "to": self.username.value, "message": msg}))
            self.messages.mount(
                Label(
                    Text.from_markup(f"[bold]{config["account"]["username"]}[/bold]\n{msg} "),
                    classes="message sent",
                )
            )
            self.messages.scroll_page_down()



app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        if is_logged_in():
            print("Run 'termxt chat' and enter friend's username to chat with them!")
        else:
            print("Please register or login with the 'termxt register' or 'termxt login'!")


@app.command()
def register():    
    if not is_logged_in():
        register = RegisterApp()
        register.run()
    else:
        print("You are logged in! Run 'termxt logout' to logout!")


@app.command()
def login():
    if not is_logged_in():
        login = LoginApp()
        login.run()
    else:
        print("You are already logged in! Run 'termxt logout' to logout!")


@app.command()
def chat():
    if is_logged_in():
        chat = ChatApp()
        chat.run()
    else:
        print("You aren't logged in! Run 'termxt login' to login in!")

@app.command()
def logout():
    if is_logged_in():
        print(f"Bye {config['account']['username']}!")
        config.clear()
        save_config()
    else:
        print("You aren't logged in!")
        
def is_logged_in():
    return config.has_section("account") and config.has_option("account", "username") and config.has_option("account", "code")

def entry():
    get_config()
    app()
    
if __name__ == "__main__":
    entry()