import os
os.environ.setdefault('SECRET_KEY', 'dev-seed-key')
os.environ.setdefault('ADMIN_PASSWORD', 'admin123')

from app import create_app
from app.db import get_db
from app.models.submissions import create_submission
from app.models.assessments import create_assessment
from app.models.notes import create_note

app = create_app()

with app.app_context():
    conn = get_db()

    # Check if data already exists
    existing = conn.execute("SELECT COUNT(*) as cnt FROM submissions").fetchone()
    if existing['cnt'] > 0:
        print("Seed data already exists, skipping.")
    else:
        # 5 sample submissions
        s1 = create_submission(conn, {
            'contact_name': 'Sarah Chen',
            'email': 'sarah@techstartup.io',
            'business_name': 'TechStartup.io',
            'business_type': 'SaaS',
            'team_size': '15-25',
            'current_workflows': 'Manual customer onboarding via email chains, spreadsheet tracking for leads',
            'pain_points': 'Onboarding takes 2 weeks, losing 30% of signups during the process',
            'tools_used': 'Gmail, Google Sheets, Notion, Slack',
            'goals': 'Reduce onboarding to 3 days, automate follow-ups',
            'urgency': 'Next 30 days - Q3 launch deadline',
            'submitter_notes': 'Attended the May workshop. Very interested in the audit.'
        })

        s2 = create_submission(conn, {
            'contact_name': 'Marcus Rivera',
            'email': 'marcus@localroasters.com',
            'business_name': 'Local Roasters Co',
            'business_type': 'Food & Beverage (Retail)',
            'team_size': '5-10',
            'current_workflows': 'Paper order forms, manual inventory counts weekly',
            'pain_points': 'Inventory mismatches, over-ordering by 20%, no visibility into trends',
            'tools_used': 'Square POS, pen and paper, Excel occasionally',
            'goals': 'Digital inventory tracking, automated reorder alerts',
            'urgency': '2-3 months',
            'submitter_notes': ''
        })

        s3 = create_submission(conn, {
            'contact_name': 'Priya Patel',
            'email': 'priya@consultinggroup.co',
            'business_name': 'Patel Consulting Group',
            'business_type': 'Professional Services',
            'team_size': '3-5',
            'current_workflows': 'Client intake via phone calls, manual proposal writing in Word',
            'pain_points': 'Spend 8 hours/week on proposals, no standardized intake process',
            'tools_used': 'Microsoft Office, Zoom, QuickBooks',
            'goals': 'Standardize intake, generate proposal drafts automatically',
            'urgency': 'Next 60 days',
            'submitter_notes': 'Referred by another workshop attendee.'
        })

        s4 = create_submission(conn, {
            'contact_name': 'James Okafor',
            'email': 'james@buildright.construction',
            'business_name': 'BuildRight Construction',
            'business_type': 'Construction',
            'team_size': '25-50',
            'current_workflows': 'Project bids via email, scheduling on whiteboards',
            'pain_points': 'Missed deadlines, double-booked crews, bid errors cost $5K+ monthly',
            'tools_used': 'Email, physical whiteboards, Excel',
            'goals': 'Digital scheduling, accurate bid calculations',
            'urgency': 'ASAP - losing money every month',
            'submitter_notes': 'Budget approved for solutions up to $2K/month.'
        })

        s5 = create_submission(conn, {
            'contact_name': 'Elena Vasquez',
            'email': 'elena@creativeagency.design',
            'business_name': 'Vasquez Creative Agency',
            'business_type': 'Creative / Marketing',
            'team_size': '8-12',
            'current_workflows': 'Client briefs via email, project tracking in Trello',
            'pain_points': 'Scope creep on 40% of projects, no time tracking',
            'tools_used': 'Trello, Figma, Slack, Google Drive',
            'goals': 'Better scope management, automated time tracking',
            'urgency': 'No rush - exploring options',
            'submitter_notes': ''
        })

        # Update some statuses directly via SQL (seed-only shortcut)
        conn.execute("UPDATE submissions SET status = 'reviewed' WHERE id = ?", (s2,))
        conn.execute("UPDATE submissions SET status = 'assessment-ready' WHERE id = ?", (s3,))
        conn.execute("UPDATE submissions SET status = 'declined' WHERE id = ?", (s5,))
        conn.commit()

        # Assessments for s1 and s3
        create_assessment(conn, s1, {
            'summary': 'Strong candidate for automation. Clear pain points with measurable impact.',
            'bottlenecks': 'Manual email-based onboarding, no CRM, spreadsheet-dependent pipeline tracking',
            'root_causes': 'Grew too fast for manual processes. No technical team to build internal tools.',
            'next_steps': '1. Map full onboarding flow. 2. Identify top 3 automation opportunities. 3. Estimate ROI.',
            'audit_fit_recommendation': 'HIGH FIT - Clear ROI story, budget available, urgent timeline.',
            'admin_notes': 'Schedule audit call for next week. Prepare onboarding flow template.'
        })

        create_assessment(conn, s3, {
            'summary': 'Good fit for intake standardization. Proposal automation is feasible with templates.',
            'bottlenecks': 'No standardized intake form, manual proposal writing, inconsistent pricing',
            'root_causes': 'Solo practitioner scaling to a small team. Processes are in founder head, not documented.',
            'next_steps': '1. Create intake questionnaire. 2. Build proposal template system. 3. Standardize pricing.',
            'audit_fit_recommendation': 'MEDIUM FIT - Lower budget, but high impact potential.',
            'admin_notes': 'Interesting case for showcasing at next workshop.'
        })

        # Mark s1 as audit fit
        conn.execute("UPDATE submissions SET is_audit_fit = 1 WHERE id = ?", (s1,))
        conn.commit()

        # Notes
        create_note(conn, s1, 'Very engaged during the workshop. Asked great questions about API integrations.')
        create_note(conn, s1, 'Follow-up call scheduled for Thursday.')
        create_note(conn, s2, 'Needs a simpler solution than what we typically recommend. Consider referring to a POS consultant.')
        create_note(conn, s4, 'High urgency but construction industry has unique scheduling constraints. Research needed.')

        print("Seed data created: 5 submissions, 2 assessments, 4 notes")
