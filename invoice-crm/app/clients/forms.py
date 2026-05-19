from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Optional, Length


class ClientForm(FlaskForm):
    name = StringField('Name', validators=[
        DataRequired(message='Client name is required.'),
        Length(max=200, message='Name must be 200 characters or fewer.')
    ])
    email = StringField('Email', validators=[
        Optional(),
        Email(message='Please enter a valid email address.'),
        Length(max=254, message='Email must be 254 characters or fewer.')
    ])
    phone = StringField('Phone', validators=[
        Optional(),
        Length(max=50, message='Phone must be 50 characters or fewer.')
    ])
    company = StringField('Company', validators=[
        Optional(),
        Length(max=200, message='Company must be 200 characters or fewer.')
    ])
    address = TextAreaField('Address', validators=[
        Optional(),
        Length(max=500, message='Address must be 500 characters or fewer.')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=2000, message='Notes must be 2000 characters or fewer.')
    ])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('lead', 'Lead')
    ], validators=[DataRequired()])
    tags = StringField('Tags (comma-separated)', validators=[
        Optional(),
        Length(max=500, message='Tags must be 500 characters or fewer.')
    ])
