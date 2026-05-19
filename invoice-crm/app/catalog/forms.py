from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, SelectField
from wtforms.validators import DataRequired, NumberRange, Optional


class CatalogItemForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    unit_price = DecimalField(
        'Unit Price ($)',
        places=2,
        validators=[DataRequired(), NumberRange(min=0)]
    )
    unit = SelectField(
        'Unit',
        choices=[
            ('hour', 'Hour'),
            ('item', 'Item'),
            ('project', 'Project'),
            ('month', 'Month'),
        ],
        validators=[DataRequired()]
    )
