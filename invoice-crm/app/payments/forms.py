from flask_wtf import FlaskForm
from wtforms import DecimalField, DateField, SelectField, TextAreaField
from wtforms.validators import DataRequired, NumberRange


class PaymentForm(FlaskForm):
    amount = DecimalField(
        'Amount ($)',
        validators=[DataRequired(), NumberRange(min=0.01, message='Amount must be greater than zero.')],
        places=2
    )
    payment_date = DateField(
        'Payment Date',
        validators=[DataRequired()],
        format='%Y-%m-%d'
    )
    method = SelectField(
        'Payment Method',
        choices=[
            ('cash', 'Cash'),
            ('check', 'Check'),
            ('bank_transfer', 'Bank Transfer'),
            ('card', 'Card'),
            ('other', 'Other'),
        ],
        validators=[DataRequired()]
    )
    notes = TextAreaField('Notes')
