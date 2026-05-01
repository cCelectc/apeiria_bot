# Styles

This directory owns application-wide style tokens and Vuetify baseline
adjustments for the authenticated management console.

Workbench UI belongs in `web/src/components/workbench/`. Feature views should
prefer those primitives for page shells, metrics, state feedback, resource
surfaces, settings sections, task dialogs, log panels, and dense data regions
before adding page-local CSS.

Use `app.css` for shared tokens such as neutral surfaces, the single primary
accent, semantic status colors, spacing, shape, motion, elevation, focus rings,
control sizing, and workbench layout variables. It may define safe Vuetify
normalization and small utility classes, but broad component behavior should
move into named workbench primitives when a pattern appears across routes.

Shape tiers are the source of truth for radius:

- `--shape-page` / `--shape-surface`: page and app shell surfaces.
- `--shape-panel`: repeated panels, dialogs, cards, filter bars, and workbench
  frames.
- `--shape-control`: inputs, buttons, segmented controls, and toolbars.
- `--shape-row`: compact list/table rows and dense metadata blocks.
- `--shape-badge`: chips, badges, pills, and count affordances.

Feature views should use these aliases directly when scoped CSS is unavoidable.
Avoid new `rounded=*` props and literal `border-radius` values unless the
component is semantically circular.

Feature scoped CSS should stay limited to domain-specific layout exceptions:
grid proportions, message composition, plugin metadata density, and similar
workflow-specific concerns. Avoid page-local gradients, one-off shadows, and
large radius rules when an existing token or workbench component can express the
hierarchy.

Navigation and copy rules live with the workbench components: keep one
tab-like layer per management route, move secondary controls into explicit
overflow or popup surfaces when needed, and avoid persistent explanatory copy
that does not support the current task. The blue Vuetify theme roles in
`plugins/vuetify.ts` are not part of routine layout cleanup.

Viewport-height workbench routes should use the shared `PageScaffold fullHeight`
behavior instead of route-local viewport math. Reserve it for pages where a
single operational surface should stay in view, such as chat, permissions,
live logs, and dense history lists. Let the inner body, list, stream, or detail
panel scroll; keep ordinary dashboard or store browsing pages on natural page
scroll unless the workflow needs a fixed frame.

Before completing a visual-system change, run `pnpm lint` and `pnpm build`, then
inspect the representative authenticated routes on desktop, tablet-width, and
mobile for horizontal overflow, clipped controls, overlap, popup usability,
localized text fit, radius drift, nested tab stacks, and drift from the shared
surface/action/filter/list conventions.
