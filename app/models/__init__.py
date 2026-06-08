# app/models/__init__.py (database agent owns this file)
# Barrel re-export: single source of truth for all model function names.
# Every function listed in the spec's Export Names Table is re-exported here
# from its owning *_models.py module, using the EXACT name from the spec.

from app.models.auth_models import (
    create_user,
    authenticate,
    get_user,
)
from app.models.project_models import (
    create_project,
    get_project,
    get_active_project,
    get_project_stats,
    transition_project_phase,
)
from app.models.scene_models import (
    create_scene,
    get_scenes,
    get_scenes_by_ids,
    get_scene,
    transition_scene_status,
    update_scene,
)
from app.models.cast_models import (
    create_cast_member,
    get_cast_members,
    get_cast_member,
    get_cast_for_scenes,
    add_cast_to_scene,
    remove_cast_from_scene,
    get_scene_cast,
)
from app.models.crew_models import (
    create_crew_member,
    get_crew_members,
    get_crew_by_department,
    get_crew_member,
)
from app.models.department_models import (
    get_departments,
    get_department,
    assign_department_head,
)
from app.models.location_models import (
    create_location,
    get_locations,
    get_location,
)
from app.models.schedule_models import (
    create_schedule_entry,
    get_schedule_entries,
    get_shoot_dates,
    reorder_schedule,
    delete_schedule_entry,
)
from app.models.callsheet_models import (
    generate_call_sheet,
    get_call_sheet,
    get_call_sheet_scenes,
    get_call_sheet_cast,
    publish_call_sheet,
)
from app.models.budget_models import (
    get_budget_summary,
    get_budget_categories,
    get_department_allocation,
    allocate_budget,
    create_line_item,
    update_line_item,
)
from app.models.expense_models import (
    create_expense,
    delete_expense,
    approve_expense,
    get_expenses,
)
from app.models.search_models import (
    search,
    index_entity,
    remove_entity,
)
from app.models.report_models import (
    get_dood_grid,
    get_production_progress,
)

__all__ = [
    # auth_models
    'create_user',
    'authenticate',
    'get_user',
    # project_models
    'create_project',
    'get_project',
    'get_active_project',
    'get_project_stats',
    'transition_project_phase',
    # scene_models
    'create_scene',
    'get_scenes',
    'get_scenes_by_ids',
    'get_scene',
    'transition_scene_status',
    'update_scene',
    # cast_models
    'create_cast_member',
    'get_cast_members',
    'get_cast_member',
    'get_cast_for_scenes',
    'add_cast_to_scene',
    'remove_cast_from_scene',
    'get_scene_cast',
    # crew_models
    'create_crew_member',
    'get_crew_members',
    'get_crew_by_department',
    'get_crew_member',
    # department_models
    'get_departments',
    'get_department',
    'assign_department_head',
    # location_models
    'create_location',
    'get_locations',
    'get_location',
    # schedule_models
    'create_schedule_entry',
    'get_schedule_entries',
    'get_shoot_dates',
    'reorder_schedule',
    'delete_schedule_entry',
    # callsheet_models
    'generate_call_sheet',
    'get_call_sheet',
    'get_call_sheet_scenes',
    'get_call_sheet_cast',
    'publish_call_sheet',
    # budget_models
    'get_budget_summary',
    'get_budget_categories',
    'get_department_allocation',
    'allocate_budget',
    'create_line_item',
    'update_line_item',
    # expense_models
    'create_expense',
    'delete_expense',
    'approve_expense',
    'get_expenses',
    # search_models
    'search',
    'index_entity',
    'remove_entity',
    # report_models
    'get_dood_grid',
    'get_production_progress',
]
