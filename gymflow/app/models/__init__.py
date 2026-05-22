# app/models/__init__.py -- Barrel file
# ALL model functions re-exported here.
# Route agents import: from app.models import function_name

from app.models.member import (
    create_member, get_member, get_all_members, get_members_by_status,
    update_member, delete_member, count_active_members,
    count_new_members_this_month, search_members,
)
from app.models.trainer import (
    create_trainer, get_trainer, get_all_trainers, get_active_trainers,
    update_trainer, delete_trainer,
)
from app.models.membership_type import (
    create_membership_type, get_membership_type, get_all_membership_types,
    get_active_membership_types, update_membership_type, delete_membership_type,
)
from app.models.class_type import (
    create_class_type, get_class_type, get_all_class_types,
    update_class_type, delete_class_type,
)
from app.models.schedule import (
    create_schedule, get_schedule, get_schedules_by_date,
    get_schedules_by_date_range, get_schedules_by_trainer,
    update_schedule, delete_schedule, copy_week_schedules,
    get_schedule_attendance_count,
)
from app.models.attendance import (
    check_in_class, check_in_open_gym, check_out, get_attendance,
    get_attendance_by_schedule, get_attendance_by_member,
    get_recent_checkins, get_today_checkins, delete_attendance,
)
from app.models.equipment import (
    create_equipment, get_equipment, get_all_equipment,
    get_equipment_by_status, update_equipment, delete_equipment,
    get_equipment_needing_maintenance,
)
from app.models.maintenance import (
    create_maintenance, get_maintenance, get_maintenance_by_equipment,
    get_all_maintenance, update_maintenance, delete_maintenance,
)
from app.models.invoice import (
    create_invoice, get_invoice, get_invoices_by_member,
    get_all_invoices, get_invoices_by_status, update_invoice,
    delete_invoice,
)
from app.models.payment import (
    create_payment, get_payment, get_payments_by_invoice,
    get_all_payments, delete_payment, get_invoice_paid_amount,
    get_revenue_this_month,
)
from app.models.assessment import (
    create_assessment, get_assessment, get_assessments_by_member,
    get_all_assessments, update_assessment, delete_assessment,
    get_latest_assessment,
)
