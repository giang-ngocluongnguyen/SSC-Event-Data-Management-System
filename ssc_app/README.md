# Special Social Event Hub — SSC demo v2

This is the second edited Streamlit demo for The Special Social Club event management system.

Run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sidebar structure

- Special Social Event Hub, with white headline text
- Internal Event Management System description
- Collapsible OVERVIEW group
  - Home
- Collapsible EVENT MANAGEMENT group
  - Create Event
  - Event Workspace
  - Event Analytics
- Collapsible DATA MANAGEMENT group
  - Database
  - Audit Log
- Divider
- The Special Social Club®
- SSC logo slot
- Operator selector: SSC Admin or Volunteer

## Pages

- `Home`: title `Special Social Event`, page pill `Home`, plain KPI metrics, max 3 upcoming/past event cards with title/divider/icon basic info, 70%-opacity teal cards, and bottom-page `Image for Event Card` upload that clears after saving.
- `Create Event`: collapsible helper forms for new location and event type, plus the main new-event form with next `event_id` preview, accessibility tick boxes, and optional event-card image upload.
- `Event Workspace`: select one event, see compact event info, register attendees, check in attendees by registration code, view checked-in attendees, collect profile completions through Google Forms upload/QR links, and run the post-event dashboard/no-show action. The selected attendee details use compact text instead of large metric cards.
- During check-in, missing required contact info (`email` and/or `phone_number`) is flagged under the selected attendee card, with a manual contact-info update option for guests or partial profiles.
- `Event Analytics`: post-event feedback QR for each event, completed feedback sheet upload/preview, and attendance table/charts.
- `Database`: inspect full tables with `last_updated`, edit/archive records, delete transactional rows, view the latest 5 audit actions, and use the Undo Action button for supported updates.
- `Audit Log`: inspect database-level trigger audit entries with table, operator, and time filters.

## Theme

- Main palette: `#c61770`, black, white, `#12a19c`, `#f6b8cf`
- Sidebar background: `#f6b8cf`
- Sidebar headline and page navigation text: dark grey on the pink sidebar, including dark mode.
- Page titles: `#c61770`
- Page-name pills: `#12a19c`
- Event cards: `rgba(18, 161, 156, 0.70)`
- Streamlit's default font is kept.

## Images

Add optional files in `assets/`:

- `ssc_logo.png` or `ssc_logo.jpg` for the sidebar logo.
- `ssc_background.png` or `ssc_background.jpg` for a background image.
- Uploaded event images are saved under `assets/event_images/` and linked through `events.event_image_path`.

The app keeps Streamlit's default font. It only adds light styling for the requested colors, cards, and controls.

## Google Forms profile completion

The `Event Workspace` page has a `Profile Completion` tab.

The app already includes the SSC Google Form field mapping from this pre-filled link:

```text
https://docs.google.com/forms/d/e/1FAIpQLSft78oYAoqBc0w_iyacr19bc0y_x6eYhOEXv-TyUoTZjOcvpA/viewform
```

When staff select an attendee, Streamlit reads that attendee's SQLite row and builds a unique Google Form link with these values already filled:

```text
event_id, event_name, participant_id, registration_id, participant_name, email, country, notes
```

The QR code points to that personalized link. During check-in, the selected attendee box includes `Generate profile QR for this attendee` when the attendee is missing contact info or their profile completeness is below the selected threshold. Staff can show the QR before check-in, and the app can also show it after a successful check-in. If `qrcode[pil]` is not installed locally, the app still displays a QR image through a browser fallback for the single-attendee preview.

In the `Profile Completion` tab, staff can review the event attendee profile-completion table and use `Update Participant Profile` to upload the completed Google Sheet export. Matching rows update the current SQLite participant records by registration code and participant ID.

If the Google Form changes later, create a new Google Forms pre-filled link and paste a placeholder template into the optional override box in the `Profile Completion` tab.

The current form link does not include a separate `registered_by` field. Add that field to Google Forms and create a new pre-filled link if you want "registered by whom" to appear as its own prefilled answer.

To update participant profiles, export the linked Google Sheet as CSV/XLSX and upload it in the same tab. Recommended columns:

```text
registration_id, participant_id, participant_name, email, phone_number, address, city, country, dob, whatsapp_groupchat, have_connect, marketing_subs
```

The app matches imported responses back to SQLite mainly by `registration_id` and `participant_id`. If a participant edits those prefilled internal fields, the row is skipped for manual review instead of silently updating the wrong person.

## Google Forms post-event feedback

The `Event Analytics` page includes a `Post-event Feedback` section. Staff select an event and the app builds that event's pre-filled feedback Google Form URL using:

```text
event_id, event_name
```

The section displays a QR code, an `Open feedback form` button, and an `Upload Completed Feedback` area for CSV/XLSX Google Sheet exports. The upload currently previews the response table and shows simple averages for numeric score columns, which keeps the demo usable without Google API credentials.
