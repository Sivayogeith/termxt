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
from config import CONFIG_FILE, API_URL, WS_URL

config = ConfigParser()


def save_config():
    with open(str(pathlib.Path.home()) + "/.termxt.cfg", "w") as config_file:
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
    def submit(self):
        response = requests.post(
            API_URL + "/user/login",
            json={"username": self.username.value, "password": self.password.value},
        )
        data = response.json()
        self.message.content = data["message"]
        if response.status_code == 200:
            config["account"] = data["data"]
            save_config()
            exit(
                "Successfully logged in! Run the chat command with your friend's username to start a chat with them!"
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
    def submit(self):
        response = requests.post(
            API_URL + "/user/register",
            json={"username": self.username.value, "password": self.password.value},
        )
        data = response.json()
        self.message.content = data["message"]
        if response.status_code == 200:
            config["account"] = data["data"]
            save_config()
            exit(
                "Successfully registered and logged in! Run the chat command with your friend's username to start a chat with them!"
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
        height: 94%;
    }

    .message {
        width: 100%;
        padding: 1;
        background: $surface;
        border-bottom: solid $panel;
        height: auto;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        self.messages = ScrollableContainer(id="message-container")
        yield self.messages
        with Container(id="input-container"):
            self.username = Input(placeholder="To username (press Enter)", id="username")
            self.message = Input(
                placeholder="Type your message here and press Enter...", id="message"
            )
            yield self.username
            yield self.message
        self.error = Label()

    def on_mount(self):
        def on_message(ws, message):
            self.call_from_thread(self.add_message, message)

        def run_ws():
            self.ws = websocket.WebSocketApp(
                WS_URL,
                on_message=on_message,
            )
            self.ws.run_forever()

        threading.Thread(target=run_ws, daemon=True).start()

    def add_message(self, message):
        message = json.loads(message)
        if message["to"] == config["account"]["username"]:
            decrypted = decrypt(message["message"], config["account"]["code"])
            self.messages.mount(
                Label(
                    Text.from_markup(f"[bold]{message["from"]}[/bold]\n{decrypted}"),
                    classes="message",
                )
            )

    @on(Input.Submitted)
    def on_send_message(self, event: Input.Submitted):
        if event.input.id == "message" and self.username_valid:
            msg = event.input.value
            event.input.value = ""
            self.ws.send(json.dumps({"from": config["account"]["username"], "to": self.username.value, "message": msg}))
        elif event.input.id == "username":
            response = requests.get(
                f"{API_URL}/user/exists?username={self.username.value}"
            )
            if int(response.text):
                self.error.update(f"{self.username.value} is a real person!")
                self.username_valid = True
            else:
                self.error.update(f"{self.username.value} doesn't exist!")
                self.username_valid = False
            self.mount(self.error)


app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        if config["account"]["code"]:
            print("Run the chat command with friend's username to chat with them!")
        else:
            print("Please register or login!")


@app.command()
def register():
    register = RegisterApp()
    register.run()


@app.command()
def login():
    login = LoginApp()
    login.run()


@app.command()
def chat():
    chat = ChatApp()
    chat.run()


if __name__ == "__main__":
    get_config()
    app()
