# CCC Congress URL Validation Prompt

Use this prompt in a Claude session with network access to validate all CCC congress URLs.

---

## Prompt for Claude:

I need you to help validate the CCC (Chaos Communication Congress) event URLs in this project. The project has recently updated URLs for congresses 37c3, 38c3, and 39c3 to match the current CCC infrastructure.

### Tasks to Complete:

1. **Run the comprehensive validation script**
   - Execute: `python scripts/validate_urls.py`
   - This script will:
     - Check HTTP status codes for all event URLs
     - Validate XML structure of schedule and podcast feeds
     - Verify that schedules contain actual events
     - Verify that podcast feeds contain media items with enclosures
     - Test all events configured in `config.yaml`

2. **Analyze the results**
   - Review any failures or warnings
   - Check if the XML structure matches expected formats:
     - **Fahrplan XML** should have: `<schedule>` → `<day>` → `<room>` → `<event>` elements
     - **Podcast XML** should have: `<rss>` → `<channel>` → `<item>` → `<enclosure>` elements
   - Identify any patterns in failures (e.g., all old events vs new events)

3. **Test the new-event command**
   - Test URL generation for a hypothetical future event:
     ```bash
     python -m media_feed new-event 2026 -c 40 --validate
     ```
   - Verify it generates URLs with the new pattern:
     - Uses lowercase "fahrplan" (not "Fahrplan")
     - Uses "mp4-hq.xml" (not "mp4.xml")

4. **Spot-check specific URLs manually**
   If any failures occur, manually fetch and inspect:
   - Check if redirects are happening (301/302)
   - Verify the actual content type is XML
   - Look for any CCC infrastructure changes

5. **Document findings**
   Create a report with:
   - Overall pass/fail status for each event
   - Any URL patterns that need updating
   - Recommendations for handling different congress eras (old vs new URL structure)
   - Any edge cases discovered (e.g., 39c3's "schedules/" directory)

### Expected Outcomes:

- **Old events (31c3-36c3)**: Should work with uppercase "Fahrplan" and "mp4.xml"
- **New events (37c3-39c3)**: Should work with lowercase "fahrplan" and "mp4-hq.xml"
- **39c3 specific**: Schedule URL includes "schedules/" directory path
- All podcast feeds should contain actual media items
- All schedules should contain actual event data

### Context:

The CCC changed their URL structure starting with 37c3 (2023):
- Directory changed: `/Fahrplan/` → `/fahrplan/`
- Podcast quality: `mp4.xml` → `mp4-hq.xml`
- 39c3 added an extra directory: `/fahrplan/schedules/schedule.xml`

The validation should confirm these patterns are correct and working.

---

## After Testing:

Please provide:
1. Full output from the validation script
2. Summary of pass/fail for each event
3. Any recommendations for config updates
4. Confirmation that new-event generation uses correct patterns
