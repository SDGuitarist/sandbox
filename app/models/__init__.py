# app/models/__init__.py
# Re-export ALL model functions from ALL model files.
# Uses try/except ImportError for each to avoid circular import issues during partial builds.

# auth_models
try:
    from app.models.auth_models import create_user
    from app.models.auth_models import authenticate
    from app.models.auth_models import get_user
except ImportError:
    pass

# project_models
try:
    from app.models.project_models import create_project
    from app.models.project_models import get_project
    from app.models.project_models import get_active_project
    from app.models.project_models import get_project_stats
    from app.models.project_models import transition_project_phase
except ImportError:
    pass

# scene_models
try:
    from app.models.scene_models import create_scene
    from app.models.scene_models import get_scenes
    from app.models.scene_models import get_scenes_by_ids
    from app.models.scene_models import get_scene
    from app.models.scene_models import transition_scene_status
    from app.models.scene_models import update_scene
except ImportError:
    pass

# cast_models
try:
    from app.models.cast_models import create_cast_member
    from app.models.cast_models import get_cast_members
    from app.models.cast_models import get_cast_member
    from app.models.cast_models import get_cast_for_scenes
    from app.models.cast_models import add_cast_to_scene
    from app.models.cast_models import remove_cast_from_scene
    from app.models.cast_models import get_scene_cast
except ImportError:
    pass

# crew_models
try:
    from app.models.crew_models import create_crew_member
    from app.models.crew_models import get_crew_members
    from app.models.crew_models import get_crew_by_department
    from app.models.crew_models import get_crew_member
except ImportError:
    pass

# department_models
try:
    from app.models.department_models import get_departments
    from app.models.department_models import get_department
    from app.models.department_models import assign_department_head
except ImportError:
    pass

# location_models
try:
    from app.models.location_models import create_location
    from app.models.location_models import get_locations
    from app.models.location_models import get_location
except ImportError:
    pass

# schedule_models
try:
    from app.models.schedule_models import create_schedule_entry
    from app.models.schedule_models import get_schedule_entries
    from app.models.schedule_models import get_shoot_dates
    from app.models.schedule_models import reorder_schedule
    from app.models.schedule_models import delete_schedule_entry
except ImportError:
    pass

# callsheet_models
try:
    from app.models.callsheet_models import generate_call_sheet
    from app.models.callsheet_models import get_call_sheet
    from app.models.callsheet_models import get_call_sheet_scenes
    from app.models.callsheet_models import get_call_sheet_cast
    from app.models.callsheet_models import publish_call_sheet
except ImportError:
    pass

# budget_models
try:
    from app.models.budget_models import get_budget_summary
    from app.models.budget_models import get_budget_categories
    from app.models.budget_models import get_department_allocation
    from app.models.budget_models import allocate_budget
    from app.models.budget_models import create_line_item
    from app.models.budget_models import update_line_item
except ImportError:
    pass

# expense_models
try:
    from app.models.expense_models import create_expense
    from app.models.expense_models import delete_expense
    from app.models.expense_models import approve_expense
    from app.models.expense_models import get_expenses
except ImportError:
    pass

# search_models
try:
    from app.models.search_models import search
    from app.models.search_models import index_entity
    from app.models.search_models import remove_entity
except ImportError:
    pass

# report_models
try:
    from app.models.report_models import get_dood_grid
    from app.models.report_models import get_production_progress
except ImportError:
    pass
