# UI/UX Design Brief
## Faculty Feedback System — Look, Feel & Interaction

**Version:** 8.0  
**Product:** Faculty Feedback System (Aditya University)  
**Platform:** Responsive web (mobile-first for students, desktop-optimised for admin/HOD/Dean)

---

## 1. Design Vision

The interface must feel **institutional, trustworthy, and calm**. Students should complete feedback in under two minutes without anxiety. Teachers should feel that results are fair and protected. Administrators and academic leaders need dense but scannable information with zero ambiguity about scope and status.

**Personality keywords:** Professional · Clear · Secure · Academic · Efficient

**Avoid:** Playful illustrations, neon gradients, dark-mode-first aesthetics, cluttered dashboards, ambiguous icons without labels.

---

## 2. Brand & Visual Identity

### 2.1 Colour Palette (Recommended)

| Role / Use | Colour | Hex (suggested) | Notes |
|------------|--------|-----------------|-------|
| Primary (actions, links) | Deep Academic Blue | `#1E3A5F` | Trust, authority |
| Primary hover / active | Richer Blue | `#152C4A` | |
| Accent (success, published) | Forest Green | `#2E7D32` | Safe, confirmed |
| Warning (open form, pending) | Amber | `#F9A825` | Attention without alarm |
| Danger / error | Soft Red | `#C62828` | Errors, destructive |
| Background page | Cool Off-White | `#F5F7FA` | Reduces eye strain |
| Surface / cards | Pure White | `#FFFFFF` | |
| Text primary | Near Black | `#1A1A1A` | High contrast |
| Text secondary | Slate Grey | `#5F6B7A` | Labels, meta |
| Borders | Light Grey | `#E2E8F0` | Subtle separation |
| Focus ring | Blue outline | `#3B82F6` | Accessibility |

University logo (Aditya) appears in header on all authenticated pages and on login screens. Prefer official logo asset already present in `static/img/aditya-logo.png`.

### 2.2 Typography

- **Headings:** System UI stack or Inter / Source Sans 3 — semi-bold, clear hierarchy (H1 24–28 px, H2 20 px, H3 16–18 px).
- **Body:** 15–16 px, line-height 1.5.
- **Monospace (codes, roll numbers):** System mono or JetBrains Mono for roll numbers and employee codes so they are easy to verify.
- **Never** use decorative script fonts.

### 2.3 Spacing & Layout

- Base unit: 8 px.
- Page max-width for content: 1120–1280 px on desktop; full width with 16 px side padding on mobile.
- Cards: 16 px padding, 8–12 px radius, light shadow or 1 px border.
- Consistent vertical rhythm between sections (24–32 px).

### 2.4 Iconography

- Simple line icons (Heroicons / Lucide style).
- Always pair icon with text label on primary actions.
- Status badges use colour + text (never colour alone).

---

## 3. Look & Feel by Role

### 3.1 Student Experience
- **Feeling:** Fast, reassuring, mobile-friendly.
- Large touch targets (min 44 px).
- Single-column form layout.
- Progress indication if multi-question forms are long.
- After submit: clear success state with checkmark and “Thank you — your feedback is anonymous”.
- Minimal navigation: Dashboard · Change Password · Logout.
- ID-card scanner affordance visible but not mandatory.

### 3.2 Teacher Experience
- **Feeling:** Professional, private, summary-first.
- Dashboard shows “Published” vs “Awaiting publication” clearly.
- Results pages emphasise aggregates (average, distribution bars) over raw lists.
- PDF download is a prominent secondary button.
- No student names or roll numbers anywhere.

### 3.3 Admin Experience
- **Feeling:** Powerful but orderly.
- Dense tables with search, filters, and bulk actions.
- Status chips (Draft / Open / Closed / Published).
- Side or top navigation covering: Dashboard, Forms, Users, Imports, Second Faculty, HOD/Dean Accounts, Requirements, Audit.
- Destructive actions (deactivate, force reset) require confirmation.

### 3.4 HOD Experience
- **Feeling:** Department ownership.
- Dashboard KPIs limited to scoped branches.
- Empty state when no scope: friendly illustration or message + “Contact administrator”.
- Form creation wizard shortened to department context only.

### 3.5 Dean Experience
- **Feeling:** Oversight and compliance.
- Higher-level charts and requirement fulfilment indicators.
- Drill-down into HOD → department, never raw student data.

---

## 4. Key Screens — Description & Behaviour

### 4.1 Login Screens (all roles)
- Centred card on soft background.
- University logo above title (“Student Login”, “Teacher Login”, etc.).
- Single primary button.
- Link to “Forgot password?”.
- Error messages appear above the form in a red-tinted alert; never below the fold.
- On mobile: full-width card, no side decoration.

### 4.2 Student Dashboard
- Greeting with roll number or name.
- Section “Pending Feedback” — cards or list rows with subject, teacher, period, “Fill now” button.
- Section “Completed” — collapsed or secondary list.
- Empty pending state: “You’re all caught up. Check back when new forms open.”

### 4.3 Feedback Form (Student)
- Header: subject name, period, teacher name (if policy allows).
- Questions in numbered sequence.
- Rating: radio buttons or star/scale selector (large enough for touch).
- Required fields marked with asterisk.
- Sticky or fixed “Submit” button on mobile.
- Confirmation dialog optional for final submit.

### 4.4 Teacher Results View
- Title: subject + period + “Published results”.
- Summary cards: response count, average overall (if applicable).
- Per-question breakdown (bar or stacked distribution).
- Anonymous comments list (if enabled) with no identifiers.
- “Download PDF” button top-right.

### 4.5 Admin Form Builder
- Step or single-page builder:
  1. Select scope / sessions
  2. Add questions (type picker)
  3. Review & Open / Save draft
- Live preview of how the student will see each question.
- Clear warning once responses exist: “Questions locked”.

### 4.6 HOD / Dean Dashboards
- Top KPI row (4–6 metric cards).
- Below: tables or lists filtered by scope.
- Consistent “Last updated” timestamp.
- Empty states are first-class designs, not afterthoughts.

---

## 5. Interaction Patterns

| Pattern | Rule |
|---------|------|
| Primary action | One obvious primary button per view (filled blue) |
| Secondary action | Outline or text button |
| Destructive | Red text or red outline + confirmation modal |
| Status change | Immediate visual feedback + flash message |
| Loading | Disable button + spinner; never silent |
| Validation | Inline under field + summary at top on submit failure |
| Tables | Sortable columns where useful; responsive card fallback on mobile |
| Modals | Used for confirmations and short forms only; escape and click-outside close |
| Toasts / flashes | Top of content area; auto-dismiss success after ~4 s; errors persist until dismissed |

---

## 6. Accessibility Requirements

- Colour contrast ≥ WCAG AA.
- All form inputs have visible labels (not placeholder-only).
- Focus order is logical; focus ring always visible.
- Buttons and links are keyboard operable.
- Error messages are associated with fields (aria-describedby or equivalent).
- Page titles change per view for screen-reader orientation.
- Scanner flow still allows full keyboard / manual fallback.

---

## 7. Responsive Behaviour

| Breakpoint | Behaviour |
|------------|-----------|
| < 640 px | Single column, bottom nav or hamburger for admin, large touch targets |
| 640–1024 px | Two-column where helpful, collapsible side nav |
| > 1024 px | Full side navigation for admin/HOD/Dean, multi-column dashboards |

Student forms must remain usable on a phone held in one hand.

---

## 8. Motion & Feedback

- Prefer subtle transitions (150–250 ms) for expand/collapse and page fades.
- No large decorative animations.
- Success: brief green check animation optional.
- Errors: gentle shake or red highlight only.

---

## 9. Content & Microcopy Tone

- Direct and respectful: “Your feedback is anonymous and cannot be traced to you.”
- Avoid jargon on student screens.
- Admin screens may use precise terms (scope, publication, eligibility).
- Empty states explain **why** and **what to do next**.
- Error messages tell the user how to recover (“Check your roll number and try again”).

---

## 10. Assets & Deliverables Checklist

- [ ] Official university logo (SVG + PNG)
- [ ] Favicon
- [ ] Status badge styles (Draft / Open / Closed / Published / Confirmed / Unresolved)
- [ ] Empty-state illustrations or icon sets (optional but recommended)
- [ ] PDF report header matching web branding
- [ ] Email template styling consistent with web (verification codes)

---

## 11. Design Principles Summary (for AI & Designers)

1. **Clarity over decoration** — every element must earn its place.
2. **Role-appropriate density** — students sparse, admin dense.
3. **Trust signals** — anonymity messaging, published badges, scope reminders.
4. **Fail visibly** — empty and error states are designed, not blank.
5. **One primary action** — reduce decision fatigue.
6. **Mobile is first-class** for the student path.

---

**This brief defines the intended look and feel.**  
All new screens must match the palette, typography, spacing, and interaction rules above.
