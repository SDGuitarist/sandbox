from flask_wtf import FlaskForm
from wtforms import (
    SelectField, StringField, TextAreaField, DateField, HiddenField
)
from wtforms.validators import DataRequired, Optional


class InvoiceForm(FlaskForm):
    """Form for creating and editing invoices.

    Line items are handled via parallel form arrays (descriptions[],
    quantities[], unit_prices[], tax_rates[], catalog_item_ids[]) and
    processed manually in the route handler -- not as WTForms fields.
    """
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    issue_date = DateField('Issue Date', validators=[DataRequired()])
    due_date = DateField('Due Date', validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])


class StatusForm(FlaskForm):
    """Form for changing invoice status."""
    new_status = HiddenField('New Status', validators=[DataRequired()])
