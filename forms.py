from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email  # requires "pip install email_validator"


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("e-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = StringField("e-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


# For admin only
class AddItemForm(FlaskForm):
    name = StringField("Item Name", validators=[DataRequired()])
    price = FloatField("Item Price", validators=[DataRequired()])
    image = StringField("Item Image Name", validators=[DataRequired()])
    amount = IntegerField("Number Available", validators=[DataRequired()])
    submit = SubmitField("Add Item")

