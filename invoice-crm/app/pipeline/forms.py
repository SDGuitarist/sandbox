from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, FloatField, IntegerField, DateField
from wtforms.validators import DataRequired, NumberRange, Optional


STAGE_CHOICES = [
    ('lead', 'Lead'),
    ('qualified', 'Qualified'),
    ('proposal', 'Proposal'),
    ('negotiation', 'Negotiation'),
    ('won', 'Won'),
    ('lost', 'Lost'),
]


class DealForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    value = FloatField('Value ($)', validators=[DataRequired(), NumberRange(min=0)])
    stage = SelectField('Stage', choices=STAGE_CHOICES, validators=[DataRequired()])
    expected_close_date = DateField('Expected Close Date', format='%Y-%m-%d', validators=[Optional()])
    probability = IntegerField('Probability (%)', validators=[DataRequired(), NumberRange(min=0, max=100)])
    notes = TextAreaField('Notes', validators=[Optional()])


class MoveDealForm(FlaskForm):
    new_stage = SelectField('New Stage', choices=STAGE_CHOICES, validators=[DataRequired()])
