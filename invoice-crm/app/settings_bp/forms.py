from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DecimalField
from wtforms.validators import DataRequired, Optional, NumberRange


class SettingsForm(FlaskForm):
    """Form for editing user business settings."""

    # Business Info
    company_name = StringField('Company Name', validators=[Optional()])
    logo_url = StringField('Logo URL', validators=[Optional()])
    address = TextAreaField('Address', validators=[Optional()])
    phone = StringField('Phone', validators=[Optional()])
    business_email = StringField('Business Email', validators=[Optional()])
    tax_id = StringField('Tax ID', validators=[Optional()])

    # Invoice Defaults
    invoice_prefix = StringField('Invoice Prefix', validators=[DataRequired()])
    default_payment_terms = SelectField(
        'Default Payment Terms',
        choices=[('15', '15 days'), ('30', '30 days'), ('60', '60 days')],
        validators=[DataRequired()]
    )
    default_tax_rate = DecimalField(
        'Default Tax Rate (%)',
        places=2,
        validators=[Optional(), NumberRange(min=0, max=100)]
    )
    currency = StringField('Currency', validators=[DataRequired()])
