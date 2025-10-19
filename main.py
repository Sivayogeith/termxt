import pathlib
from textual import on
import typer
from textual.app import App, ComposeResult
from textual.widgets import Input, Button, Label
import requests
from configparser import ConfigParser

from config import CONFIG_FILE, API_URL

config = ConfigParser()

def save_config(): 
    with open(str(pathlib.Path.home()) + "/.termxt.cfg", 'w') as config_file:
        config.write(config_file)

def get_config(): 
    config.read(pathlib.Path.home() + CONFIG_FILE)

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
        response = requests.post(API_URL+"/user/login", json = {"username": self.username.value, "password": self.password.value})
        data = response.json()
        self.message.content = data["message"]
        if (response.status_code == 200):
            config["account"] = data["data"]
            save_config()
            exit("Successfully logged in! Run the chat command with your friends code to start a chat with them!")
            
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
        response = requests.post(API_URL+"/user/register", json = {"username": self.username.value, "password": self.password.value})
        data = response.json()
        self.message.content = data["message"]
        if (response.status_code == 200):
            config["account"] = data["data"]
            save_config()
            exit("Successfully registered and logged in! Run the chat command with your friends code to start a chat with them!")
            
app = typer.Typer()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print("Register pls")

@app.command()
def register():
    register = RegisterApp()
    register.run()

@app.command()
def login():
    login = LoginApp()
    login.run()


if __name__ == "__main__":
    app()