from datetime import date, datetime
from flask import render_template, request, redirect, url_for, flash, abort
from . import bp
from ..db import get_db
from ..decorators import setup_required

# Pipeline stages: (key, label, probability_pct)
PIPELINE_STAGES = [
    ('lead', 'Lead', 10),
    ('discovery', 'Discovery', 25),
    ('proposal_sent', 'Proposal Sent', 50),
    ('negotiation', 'Negotiation', 65),
    ('verbal_yes', 'Verbal Yes', 80),
    ('won', 'Won', 100),
    ('lost', 'Lost', 0),
]

STAGE_MAP = {s[0]: {'label': s[1], 'probability': s[2]} for s in PIPELINE_STAGES}

# Active stages for the board view (exclude won/lost)
BOARD_STAGES = [s for s in PIPELINE_STAGES if s[0] not in ('won', 'lost')]


@bp.route('/')
@setup_required
def board():
    """Kanban board view of the pipeline. Shows active stages only (no won/lost)."""
    with get_db() as db:
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()

        stages = []
        for key, label, probability in BOARD_STAGES:
            deals = db.execute(
                "SELECT d.*, c.name as contact_name "
                "FROM deal d LEFT JOIN contact c ON d.contact_id = c.id "
                "WHERE d.stage = ? ORDER BY d.updated_at DESC",
                (key,)
            ).fetchall()
            total_value = sum(d['value'] for d in deals)
            weighted_value = sum(d['value'] * probability // 100 for d in deals)
            stages.append({
                'key': key,
                'label': label,
                'probability': probability,
                'deals': deals,
                'total_value': total_value,
                'weighted_value': weighted_value,
            })

    return render_template('pipeline/board.html', stages=stages, contacts=contacts)


@bp.route('/list')
@setup_required
def list_view():
    """Table list view of all deals."""
    with get_db() as db:
        deals = db.execute(
            "SELECT d.*, c.name as contact_name, co.name as company_name "
            "FROM deal d "
            "LEFT JOIN contact c ON d.contact_id = c.id "
            "LEFT JOIN company co ON d.company_id = co.id "
            "ORDER BY d.updated_at DESC "
            "LIMIT 1000"
        ).fetchall()

    return render_template('pipeline/list.html', deals=deals, stages=PIPELINE_STAGES)


@bp.route('/<int:id>')
@setup_required
def detail(id):
    """Detail view for a single deal."""
    with get_db() as db:
        deal = db.execute("SELECT * FROM deal WHERE id = ?", (id,)).fetchone()
        if not deal:
            abort(404)

        contact = None
        if deal['contact_id']:
            contact = db.execute(
                "SELECT * FROM contact WHERE id = ?", (deal['contact_id'],)
            ).fetchone()

        company = None
        if deal['company_id']:
            company = db.execute(
                "SELECT * FROM company WHERE id = ?", (deal['company_id'],)
            ).fetchone()

    return render_template(
        'pipeline/detail.html',
        deal=deal,
        contact=contact,
        company=company,
        stages=PIPELINE_STAGES,
    )


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    """Create a new deal."""
    with get_db() as db:
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()
        companies = db.execute("SELECT id, name FROM company ORDER BY name").fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash("Title is required.", "error")
            return render_template(
                'pipeline/form.html',
                deal=None,
                contacts=contacts,
                companies=companies,
                stages=PIPELINE_STAGES,
                sources=['referral', 'website', 'social', 'cold_outreach', 'other'],
            )

        contact_id = request.form.get('contact_id') or None
        if contact_id:
            contact_id = int(contact_id)
        company_id = request.form.get('company_id') or None
        if company_id:
            company_id = int(company_id)

        value_str = request.form.get('value', '0')
        try:
            value = int(float(value_str) * 100)
        except (ValueError, TypeError):
            value = 0

        stage = request.form.get('stage', 'lead')
        if stage not in STAGE_MAP:
            stage = 'lead'
        probability_pct = STAGE_MAP[stage]['probability']

        expected_close_date = request.form.get('expected_close_date', '').strip() or None
        notes = request.form.get('notes', '').strip()
        source = request.form.get('source', '').strip()

        with get_db(immediate=True) as db:
            db.execute(
                "INSERT INTO deal (title, contact_id, company_id, value, stage, "
                "probability_pct, expected_close_date, notes, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, contact_id, company_id, value, stage,
                 probability_pct, expected_close_date, notes, source),
            )
            deal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('created', 'deal', deal_id, f"Created deal {title}"),
            )

        flash("Deal created successfully.", "success")
        return redirect(url_for('pipeline.detail', id=deal_id))

    return render_template(
        'pipeline/form.html',
        deal=None,
        contacts=contacts,
        companies=companies,
        stages=PIPELINE_STAGES,
        sources=['referral', 'website', 'social', 'cold_outreach', 'other'],
    )


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    """Edit an existing deal."""
    with get_db() as db:
        deal = db.execute("SELECT * FROM deal WHERE id = ?", (id,)).fetchone()
        if not deal:
            abort(404)
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()
        companies = db.execute("SELECT id, name FROM company ORDER BY name").fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash("Title is required.", "error")
            return render_template(
                'pipeline/form.html',
                deal=deal,
                contacts=contacts,
                companies=companies,
                stages=PIPELINE_STAGES,
                sources=['referral', 'website', 'social', 'cold_outreach', 'other'],
            )

        contact_id = request.form.get('contact_id') or None
        if contact_id:
            contact_id = int(contact_id)
        company_id = request.form.get('company_id') or None
        if company_id:
            company_id = int(company_id)

        value_str = request.form.get('value', '0')
        try:
            value = int(float(value_str) * 100)
        except (ValueError, TypeError):
            value = 0

        stage = request.form.get('stage', deal['stage'])
        if stage not in STAGE_MAP:
            stage = deal['stage']
        probability_pct = STAGE_MAP[stage]['probability']

        expected_close_date = request.form.get('expected_close_date', '').strip() or None
        notes = request.form.get('notes', '').strip()
        source = request.form.get('source', '').strip()
        loss_reason = request.form.get('loss_reason', '').strip() or None

        with get_db(immediate=True) as db:
            db.execute(
                "UPDATE deal SET title=?, contact_id=?, company_id=?, value=?, stage=?, "
                "probability_pct=?, expected_close_date=?, notes=?, source=?, loss_reason=?, "
                "updated_at=datetime('now') WHERE id=?",
                (title, contact_id, company_id, value, stage,
                 probability_pct, expected_close_date, notes, source, loss_reason, id),
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'deal', id, f"Updated deal {title}"),
            )

        flash("Deal updated successfully.", "success")
        return redirect(url_for('pipeline.detail', id=id))

    return render_template(
        'pipeline/form.html',
        deal=deal,
        contacts=contacts,
        companies=companies,
        stages=PIPELINE_STAGES,
        sources=['referral', 'website', 'social', 'cold_outreach', 'other'],
    )


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    """Delete a deal."""
    with get_db(immediate=True) as db:
        deal = db.execute("SELECT title FROM deal WHERE id = ?", (id,)).fetchone()
        if not deal:
            abort(404)
        db.execute("DELETE FROM deal WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('deleted', 'deal', id, f"Deleted deal {deal['title']}"),
        )

    flash("Deal deleted.", "success")
    return redirect(url_for('pipeline.board'))


@bp.route('/<int:id>/move', methods=['POST'])
@setup_required
def move_stage(id):
    """Move a deal to a new stage. Special handling for won/lost."""
    stage = request.form.get('stage', '').strip()
    if stage not in STAGE_MAP:
        flash("Invalid stage.", "error")
        return redirect(url_for('pipeline.board'))

    with get_db(immediate=True) as db:
        deal = db.execute("SELECT * FROM deal WHERE id = ?", (id,)).fetchone()
        if not deal:
            abort(404)

        stage_label = STAGE_MAP[stage]['label']
        probability_pct = STAGE_MAP[stage]['probability']

        if stage == 'lost':
            loss_reason = request.form.get('loss_reason', '').strip()
            if not loss_reason:
                flash("Loss reason is required when marking a deal as lost.", "error")
                return redirect(url_for('pipeline.detail', id=id))

            db.execute(
                "UPDATE deal SET stage=?, probability_pct=?, loss_reason=?, "
                "updated_at=datetime('now') WHERE id=?",
                (stage, probability_pct, loss_reason, id),
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('lost', 'deal', id, f"Lost deal {deal['title']}"),
            )
            flash(f"Deal marked as lost.", "warning")
            return redirect(url_for('pipeline.board'))

        if stage == 'won':
            db.execute(
                "UPDATE deal SET stage=?, probability_pct=?, updated_at=datetime('now') WHERE id=?",
                (stage, probability_pct, id),
            )
            # Format value for activity log using dollars filter logic
            value_dollars = f"${deal['value'] / 100:,.2f}"
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('won', 'deal', id, f"Won deal {deal['title']} ({value_dollars})"),
            )
            flash(f"Deal won! Create a project for it.", "success")
            return redirect(url_for('projects.create', deal_id=id))

        # Normal stage move
        db.execute(
            "UPDATE deal SET stage=?, probability_pct=?, updated_at=datetime('now') WHERE id=?",
            (stage, probability_pct, id),
        )
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('moved', 'deal', id, f"Moved deal {deal['title']} to {stage_label}"),
        )

    flash(f"Deal moved to {stage_label}.", "success")
    return redirect(url_for('pipeline.board'))


@bp.route('/stats')
@setup_required
def stats():
    """Pipeline statistics page."""
    with get_db() as db:
        # Stage stats: count, total value, weighted value per stage
        stage_stats = []
        for key, label, probability in PIPELINE_STAGES:
            row = db.execute(
                "SELECT COUNT(*) as count, COALESCE(SUM(value), 0) as total_value "
                "FROM deal WHERE stage = ?",
                (key,),
            ).fetchone()
            weighted = row['total_value'] * probability // 100
            stage_stats.append({
                'key': key,
                'label': label,
                'probability': probability,
                'count': row['count'],
                'total_value': row['total_value'],
                'weighted_value': weighted,
            })

        # Total weighted pipeline value (active stages only, exclude won/lost)
        total_weighted = sum(
            s['weighted_value'] for s in stage_stats
            if s['key'] not in ('won', 'lost')
        )

        # Deals closing this month
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        if today.month == 12:
            next_month_start = today.replace(year=today.year + 1, month=1, day=1).isoformat()
        else:
            next_month_start = today.replace(month=today.month + 1, day=1).isoformat()

        closing_this_month = db.execute(
            "SELECT d.*, c.name as contact_name "
            "FROM deal d LEFT JOIN contact c ON d.contact_id = c.id "
            "WHERE d.expected_close_date >= ? AND d.expected_close_date < ? "
            "AND d.stage NOT IN ('won', 'lost') "
            "ORDER BY d.expected_close_date",
            (month_start, next_month_start),
        ).fetchall()

        # Win rate: won / (won + lost) * 100
        won_count = db.execute(
            "SELECT COUNT(*) as c FROM deal WHERE stage = 'won'"
        ).fetchone()['c']
        lost_count = db.execute(
            "SELECT COUNT(*) as c FROM deal WHERE stage = 'lost'"
        ).fetchone()['c']
        total_closed = won_count + lost_count
        win_rate = (won_count / total_closed * 100) if total_closed > 0 else 0.0

    return render_template(
        'pipeline/stats.html',
        stage_stats=stage_stats,
        total_weighted=total_weighted,
        closing_this_month=closing_this_month,
        win_rate=win_rate,
    )
