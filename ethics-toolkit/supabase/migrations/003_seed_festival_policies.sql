-- Seed festival_policies with 12 records from Section 4 Tool 2
-- Spec reference: Section 4 Tool 2 -- Seed Data

INSERT INTO festival_policies (festival_name, year, ai_policy, policy_details, source_url, last_reviewed_date, confidence_level, categories)
VALUES
  (
    'Cannes Film Festival',
    2026,
    'banned',
    'Generative AI for scripting, visuals, or performances makes films ineligible for the Palme d''Or and Official Competition. Technical AI (sound restoration, VFX cleanup) still allowed.',
    'https://www.festival-cannes.com/en/rules',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'TIFF (Toronto International Film Festival)',
    2026,
    'disclosure_required',
    'Must disclose which components use AI. Failure may result in disqualification.',
    'https://www.tiff.net/submissions',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'Sundance Film Festival',
    2026,
    'disclosure_required',
    'Ask how you used AI on submission form. Treated as research data, not gatekeeping. Voluntary but strongly encouraged.',
    'https://www.sundance.org/festivals/sundance-film-festival/submit',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'Berlinale (Berlin International Film Festival)',
    2026,
    'disclosure_required',
    'Asks about AI usage in submission. Treats disclosure as informational, not disqualifying.',
    'https://www.berlinale.de/en/festival/programme/submission.html',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'SXSW Film & TV Festival',
    2026,
    'disclosure_required',
    'Requires disclosure of AI usage in submission materials. No blanket ban.',
    'https://www.sxsw.com/film/submissions/',
    '2026-04-15',
    'inferred',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'Venice Film Festival',
    2026,
    'no_stated_policy',
    'No explicit AI policy published as of last review. Check current submission guidelines.',
    'https://www.labiennale.org/en/cinema',
    '2026-04-15',
    'unverified',
    ARRAY[]::TEXT[]
  ),
  (
    'Tribeca Festival',
    2026,
    'disclosure_required',
    'Asks about AI/immersive technology usage. Has dedicated immersive/new media category.',
    'https://tribecafilm.com/festival/submissions',
    '2026-04-15',
    'inferred',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'CREDO 23 / No AI Allowed Festival',
    2026,
    'banned',
    'Strictly human-made films only. Founded by Justine Bateman, Reed Morano, Matthew Weiner, Juliette Lewis. Zero tolerance for any AI-generated content.',
    'https://www.noaiallowed.com',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    'Sato48 Springfield',
    2026,
    'restricted',
    'AI may be used for pre-production and planning only. Final deliverable must be human-created.',
    'https://sato48.com/rules',
    '2026-04-15',
    'verified',
    ARRAY['writing','storyboard']
  ),
  (
    'Cannes Lions (Advertising)',
    2026,
    'disclosure_required',
    'Mandatory disclosure of AI components in advertising entries. Failure may result in disqualification.',
    'https://www.canneslions.com/enter/rules',
    '2026-04-15',
    'verified',
    ARRAY['writing','music','vfx','voice']
  ),
  (
    '48 Hour Film Project',
    2026,
    'restricted',
    'AI-generated music rules under active review. Policy being escalated to global HQ. Check local chapter rules.',
    'https://www.48hourfilm.com/rules',
    '2026-04-27',
    'inferred',
    ARRAY['music']
  ),
  (
    'San Diego Streaming Film Festival (SDSFF)',
    2026,
    'no_stated_policy',
    'No explicit AI policy. Michael Howard (organizer) open to AI discussion. Alex delivered workshop April 4 and April 11.',
    'https://www.sdstreamingfilmfestival.com',
    '2026-04-11',
    'verified',
    ARRAY[]::TEXT[]
  );
