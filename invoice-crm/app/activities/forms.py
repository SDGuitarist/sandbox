from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, DateField
from wtforms.validators import DataRequired
from datetime import date


class ActivityForm(FlaskForm):
    type = SelectField(
        'Type',
        choices=[
            ('call', 'Call'),
            ('email', 'Email'),
            ('meeting', 'Meeting'),
            ('note', 'Note'),
        ],
        validators=[DataRequired()],
    )
    notes = TextAreaField('Notes')
    activity_date = DateField(
        'Date',
        format='%Y-%m-%d',
        default=date.today,
        validators=[DataRequired()],
    )
