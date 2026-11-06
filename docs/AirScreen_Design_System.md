# AirScreen Design System
## Engineering-grade UI/UX specification — Windows Sender + Android TV Receiver

**Version:** 1.1.0  
**Status:** Product design and implementation specification  
**Audience:** Product design, senior frontend engineering, Windows engineering, Android engineering, QA  
**Platforms:** Windows desktop sender; Android TV receiver  
**Visual direction:** Premium dark, cinematic, restrained, 3D iconography only

---

# 0. Purpose and product principles

This is the implementation source of truth for AirScreen's visual foundations, component behaviour, motion, interaction states, platform layouts, accessibility, and 3D icon system.

AirScreen has two distinct interaction environments:

- **Windows sender:** information-rich, precise, keyboard/mouse friendly, and diagnostic-capable.
- **Android TV receiver:** cinematic, minimal, readable from a distance, and fully operable by D-pad remote.

Share the brand and semantic tokens across platforms. Do not force identical layouts or interactions.

## 0.1 Product principles

1. Streaming is the primary task.
2. Connection states must always be explicit and truthful.
3. TV is a 10-foot interface, not a scaled desktop app.
4. Windows should be powerful without feeling like an admin console.
5. Motion communicates state; it is not decoration.
6. 3D iconography is the only approved icon style. No flat 2D, outline, sketch, hand-drawn, or mixed icon families.
7. The 3D icon system must remain restrained, consistent, legible, and performant.
8. Telemetry must distinguish configured, negotiated, measured, and estimated values.
9. Accessibility and reduced-motion behaviour are part of each component contract.
10. Prefer native platform behaviour where it improves usability.

## 0.2 Non-goals

- No generic media-player aesthetic.
- No dense TV settings tables.
- No excessive glass blur, neon glow, or animated backgrounds.
- No unverified codec, resolution, FPS, latency, or network claims.
- No decorative 3D objects that compete with the primary task.
- No flat, outline, sketch, or hand-drawn icons anywhere in the product UI.

---

# 1. Brand identity and visual language

| Attribute | Specification |
|---|---|
| Product | AirScreen |
| Category | Wireless screen streaming |
| Personality | Calm, capable, precise, dependable |
| Visual character | Premium dark surfaces, restrained violet/cyan accents |
| Iconography | Consistent dimensional 3D icons |
| Density | Medium on Windows; low on TV |
| Motion | Fast, purposeful, consistent |
| Shape | Softly rounded, not excessively pill-shaped |

## 1.1 Logo

- Use one master AirScreen mark and wordmark across platforms.
- Keep the mark legible at 20–24 px in desktop navigation and 40–56 px in TV hero areas.
- Use a monochrome light mark only when the full-colour mark loses contrast.
- Never distort, rotate, bevel, extrude, or add unapproved effects to the logo.
- Keep clear space equal to at least 25% of the mark's height.
- Provide SVG assets for the logo; the 3D-only rule applies to interface icons, not the brand mark or typography.

## 1.2 Visual restraint

Use the brand gradient for primary actions, active navigation accents, selected states, and limited brand highlights. Do not turn every card, icon, or surface into a gradient.

Use 3D icons as purposeful visual anchors. Do not place a large 3D illustration beside every label. Small controls may use a simplified dimensional icon variant while retaining the same 3D construction language.

---

# 2. Design tokens

Tokens are the only approved source of repeated visual values. Components must consume tokens rather than hard-code colours, spacing, radii, or motion values.

## 2.1 Brand colours

| Token | Value | Usage |
|---|---|---|
| `color.brand.primary` | `#8057FF` | Primary action, selected accent |
| `color.brand.primaryHover` | `#916EFF` | Hover |
| `color.brand.primaryPressed` | `#7046ED` | Pressed |
| `color.brand.primarySubtle` | `#241B43` | Selected surface |
| `color.brand.secondary` | `#318BFF` | Secondary accent |
| `color.brand.cyan` | `#22D3EE` | Network/technical accent |
| `color.brand.gradient` | `#8057FF → #A855F7` | Primary brand gradient |

## 2.2 Dark neutral palette

| Token | Value | Usage |
|---|---|---|
| `color.bg.canvas` | `#080B16` | App background |
| `color.bg.sidebar` | `#0D1222` | Sidebar |
| `color.bg.surface` | `#11182A` | Main panels |
| `color.bg.surfaceRaised` | `#171F34` | Cards |
| `color.bg.surfaceOverlay` | `#202A42` | Menus/popovers |
| `color.bg.input` | `#0B1120` | Inputs |
| `color.border.subtle` | `#202A40` | Subtle border |
| `color.border.default` | `#2A3650` | Standard border |
| `color.border.strong` | `#43516E` | Strong border |
| `color.text.primary` | `#F7F8FC` | Primary text |
| `color.text.secondary` | `#B3BDD0` | Supporting text |
| `color.text.tertiary` | `#8491AA` | Metadata |
| `color.text.disabled` | `#59657C` | Disabled text |

## 2.3 Semantic colours

| Token | Value | Meaning |
|---|---|---|
| `color.status.success` | `#34D399` | Ready/connected/healthy |
| `color.status.warning` | `#FBBF24` | Degraded/attention |
| `color.status.danger` | `#F87171` | Failed/disconnected/denied |
| `color.status.info` | `#60A5FA` | Informational |
| `color.status.neutral` | `#94A3B8` | Unknown/inactive |

Status must include text or an icon; never communicate state through colour alone.

## 2.4 Gradients

```css
:root {
  --gradient-brand: linear-gradient(135deg, #8057FF 0%, #A855F7 100%);
  --gradient-cool: linear-gradient(135deg, #318BFF 0%, #22D3EE 100%);
  --gradient-ambient:
    radial-gradient(ellipse at 18% 85%, rgba(128,87,255,.16), transparent 42%),
    radial-gradient(ellipse at 82% 78%, rgba(34,211,238,.10), transparent 40%);
}
```

Ambient gradients are static, low-contrast decoration. Do not animate full-screen gradients continuously.

## 2.5 Typography

**Preferred:** Inter.  
**Windows fallback:** Segoe UI Variable, Segoe UI, sans-serif.  
**Android fallback:** Roboto, sans-serif.

### Windows scale

| Token | Size / line height | Weight | Usage |
|---|---|---|---|
| Display | 36 / 44 px | 700 | Hero |
| H1 | 28 / 36 px | 650 | Page title |
| H2 | 22 / 30 px | 600 | Section |
| H3 | 17 / 24 px | 600 | Card title |
| Body | 14 / 21 px | 400 | Body |
| Body strong | 14 / 21 px | 600 | Emphasis |
| Label | 12 / 16 px | 600 | Field label |
| Caption | 12 / 16 px | 400 | Metadata |
| Micro | 10 / 14 px | 500 | Technical metadata only |

### Android TV scale

Use `sp` and validate on the actual television at viewing distance.

| Token | Starting size | Weight |
|---|---:|---|
| TV Display | 44 sp | 700 |
| TV H1 | 34 sp | 700 |
| TV H2 | 26 sp | 600 |
| TV H3 | 22 sp | 600 |
| TV Body | 20 sp | 400 |
| TV Label | 18 sp | 500 |
| TV Caption | 16 sp | 400 |

No micro text on TV. Use tabular numerals for pairing codes, FPS, bitrate, and latency.

## 2.6 Spacing

4 px base scale.

| Token | Value |
|---|---:|
| `space.1` | 4 px |
| `space.2` | 8 px |
| `space.3` | 12 px |
| `space.4` | 16 px |
| `space.5` | 20 px |
| `space.6` | 24 px |
| `space.8` | 32 px |
| `space.10` | 40 px |
| `space.12` | 48 px |
| `space.16` | 64 px |
| `space.20` | 80 px |

Use 8/16/24/32 px for most layout rhythm. Larger gaps separate sections; smaller gaps group labels and values.

## 2.7 Radius, borders, elevation

| Token | Value |
|---|---:|
| `radius.xs` | 4 px |
| `radius.sm` | 8 px |
| `radius.md` | 12 px |
| `radius.lg` | 16 px |
| `radius.xl` | 20 px |
| `radius.2xl` | 24 px |
| `radius.pill` | 999 px |

```css
:root {
  --border-subtle: 1px solid rgba(255,255,255,.05);
  --border-default: 1px solid rgba(255,255,255,.08);
  --border-strong: 1px solid rgba(255,255,255,.14);
  --shadow-card: 0 8px 24px rgba(0,0,0,.20);
  --shadow-popover: 0 16px 40px rgba(0,0,0,.34);
  --shadow-dialog: 0 24px 64px rgba(0,0,0,.48);
  --shadow-focus: 0 0 0 3px rgba(128,87,255,.34);
}
```

Use borders before shadows to define surfaces. Avoid stacked shadows and excessive glow.

---

# 3. 3D iconography system — mandatory

**This section is a product-wide requirement. Every interface icon must follow this 3D visual language.**

## 3.1 Core rule

- All UI icons must be dimensional 3D assets.
- No flat 2D icons.
- No outline-only icons.
- No sketch, hand-drawn, doodle, or wireframe icons.
- No mixing Lucide/Feather/Material outline icons with 3D assets.
- Do not use emoji as production icons.
- Do not use random stock icon packs with inconsistent lighting or geometry.
- Use a single coherent 3D icon family, created or commissioned specifically for AirScreen.

This requirement applies to navigation, buttons, status indicators, device types, settings categories, empty states, and feature illustrations. Text glyphs and native window controls are not considered icons, but must remain visually compatible.

## 3.2 Art direction

The AirScreen 3D icon style is:

- Premium, minimal, soft 3D.
- Rounded geometric forms with controlled bevels.
- Physically plausible soft studio lighting.
- Subtle material depth and ambient occlusion.
- Restrained violet, indigo, blue, and cyan accents.
- Dark-neutral or transparent background depending on placement.
- Smooth surfaces; no noisy textures.
- No exaggerated cartoon faces or toy-like proportions.
- No sharp, aggressive sci-fi spikes.
- No excessive bloom or lens flare.
- No text embedded inside icon artwork.

Think **high-end product-render iconography**, not cartoon stickers and not flat vector symbols.

## 3.3 Geometry and construction

- Use a consistent 24-unit conceptual grid for small icons.
- Keep the visual centre optically aligned.
- Use consistent apparent depth and bevel radius across the family.
- Keep silhouettes recognisable at 24–32 px.
- Avoid details that disappear at small sizes.
- For small controls, use simplified 3D geometry rather than shrinking a complex hero illustration.
- Preserve consistent perspective across the set (prefer a restrained three-quarter/isometric view for object icons; front-facing or slight perspective for UI symbols).
- Maintain consistent object scale within a category.

## 3.4 Materials and lighting

Approved materials:
- Satin ceramic.
- Soft-touch matte polymer.
- Frosted translucent acrylic, used sparingly.
- Anodised metal accents, used sparingly.
- Subtle emissive accent surfaces for active/connected states only.

Lighting:
- One large soft key light from upper-left.
- Gentle fill from the opposite side.
- Very subtle rim light where separation is needed.
- Soft contact shadow / ambient occlusion.
- Consistent light direction across every asset.

Do not use:
- Hard specular hotspots.
- Metallic chrome on every icon.
- Strong glass refraction that reduces silhouette clarity.
- Heavy bloom.
- Multi-directional inconsistent lighting.

## 3.5 Colour treatment

- Main body: neutral graphite, deep indigo, or muted slate.
- Accent: violet/blue/cyan details.
- Success: restrained emerald accent.
- Warning: restrained amber accent.
- Error: restrained coral/red accent.
- Avoid rainbow gradients on individual icons.
- Semantic colour should appear as a small controlled accent, not recolour the whole object.

## 3.6 Icon sizes and exports

| Context | Display size | Asset guidance |
|---|---:|---|
| Windows compact action | 20–24 px | Simplified 3D |
| Windows navigation | 24–28 px | 3D icon, clear silhouette |
| Windows feature card | 40–56 px | Medium-detail 3D |
| Windows empty state | 72–112 px | 3D illustration |
| TV navigation | 32–40 dp | High-contrast simplified 3D |
| TV action | 40–56 dp | Medium-detail 3D |
| TV hero/state | 96–160 dp | Hero 3D illustration |

Export:
- SVG only for the AirScreen logo and non-icon vector brand assets.
- 3D UI icons: WebP or AVIF with alpha where supported; PNG fallback where required.
- Use 1x/2x/3x variants or density-aware asset generation.
- Prefer transparent backgrounds for icons placed on variable surfaces.
- Use consistent padding in the asset canvas so different icons have comparable optical size.
- Keep source 3D files (e.g. Blender project) in the asset source directory.
- Store metadata: asset name, dimensions, version, source file, and intended usage.

## 3.7 3D icon interaction states

Do not distort or spin icons on every hover.

| State | Behaviour |
|---|---|
| Default | Static 3D icon with soft shading |
| Hover (Windows) | Small luminance increase; optional 1–2% scale |
| Focus (Windows/TV) | Icon remains stable; focus ring belongs to control container |
| Pressed | Brief 0.97–0.99 scale on control; icon may move no more than 1 px |
| Selected | Small controlled accent light/material change |
| Disabled | Lower contrast and saturation; preserve recognisable silhouette |
| Loading | Use a dedicated progress indicator, not a spinning 3D icon |
| Success | Optional short accent fade; no continuous pulse |
| Error | Semantic accent or adjacent status text; do not shake repeatedly |

## 3.8 Animation of 3D assets

- Default icon state is static.
- Hover animation is subtle and short (100–160 ms).
- Avoid continuous rotation, floating, wobble, bounce, or breathing effects.
- A single short reveal animation is acceptable for a major empty state or onboarding illustration.
- Respect reduced motion.
- Do not animate 3D assets while fullscreen video is playing.
- Keep animation off the critical streaming/rendering path.

## 3.9 Required AirScreen icon inventory

Create a consistent asset family for:

### Core navigation
- Cast
- Devices
- Streaming
- Settings
- Logs
- About

### Device and connection
- Television receiver
- Windows desktop
- Laptop
- Network/Wi-Fi
- Ethernet
- Device discovery
- Pairing
- Secure connection
- Connection lost
- Reconnecting

### Media and streaming
- Display/screen
- Window capture
- Application capture
- Video
- Audio
- Mute
- Volume
- Resolution
- Frame rate
- Bitrate
- Latency
- Pause
- Resume
- Stop

### Security and diagnostics
- Shield/security
- Encryption
- Authentication
- Warning
- Error
- Health/diagnostics
- Log file
- Export
- Refresh/rescan
- Help

Use semantic names in code, for example `icon-device-tv`, `icon-stream-video`, `icon-network-wifi`, `icon-security-shield`. Do not name assets by colour or appearance alone.

## 3.10 Icon fallback policy

If a 3D asset is not yet available:
1. Use a text label without an icon, or
2. Use a neutral placeholder container with no symbol.

Do not temporarily substitute a flat 2D icon and allow it to ship. A missing 3D asset is preferable to a visually inconsistent icon family.

## 3.11 3D asset quality gate

An icon is approved only when:
- It matches the AirScreen lighting direction.
- Its apparent depth and bevels match the family.
- It remains recognisable at its smallest target size.
- It has a clean silhouette against all approved surfaces.
- It has transparent/appropriate background handling.
- It has no accidental text or watermark.
- It does not rely on glow to be legible.
- It has normal, disabled, and semantic-state usage guidance.
- It has been checked on Windows and TV display densities.
- It passes reduced-motion and performance review if animated.

---

# 4. Layout systems

## 4.1 Windows desktop shell

Target Windows 11. Support window resizing and high-DPI scaling.

- Sidebar: 224 px expanded; compact 72 px only if required.
- Page padding: 28–32 px.
- Section spacing: 24 px.
- Card gap: 16–20 px.
- Minimum practical window: 960 × 640 logical px.
- Collapse secondary panels before hiding primary actions.
- Keep scrolling in the main content region; avoid nested scrolling without clear purpose.
- Preserve native title-bar/window-control expectations.

Use a 12-column conceptual grid at wide widths. Prefer content-driven columns over rigid fixed widths.

### Windows navigation

1. Cast
2. Devices
3. Streaming
4. Settings
5. Logs
6. About

Selected, hover, and keyboard focus states must be distinct.

## 4.2 Android TV layout

- Reference canvas: 1920 × 1080.
- Start with approximately 5% horizontal safe margins.
- Use responsive constraints and density-independent units.
- Keep important text and controls away from display edges.
- Large controls, low density, clear spatial grouping.
- No hover-only interactions.
- Validate on the real Sony BRAVIA TV and remote.

### D-pad requirements

- Every interactive item is focusable.
- Define deterministic directional focus.
- No focus traps.
- Initial focus is intentional.
- Dialog focus enters and returns to its trigger.
- Focus must not jump when discovery results refresh.
- Disabled controls are skipped unless focus is needed to explain unavailability.

---

# 5. Motion and interaction system

## 5.1 Motion principles

- Immediate feedback.
- No fake waiting.
- Consistent direction and easing.
- State changes are animated only when it improves comprehension.
- Reduced-motion path is mandatory.
- Never animate the video surface.
- TV motion must be visible but not sluggish.

## 5.2 Duration tokens

| Token | Duration | Usage |
|---|---:|---|
| `motion.instant` | 80 ms | Press feedback |
| `motion.fast` | 120 ms | Hover/icon feedback |
| `motion.normal` | 180 ms | Button/card |
| `motion.medium` | 240 ms | Menu/panel |
| `motion.slow` | 320 ms | Dialog/route |
| `motion.emphasis` | 420 ms | Rare major transition |

Avoid ordinary control animations longer than 500 ms.

## 5.3 Easing

```css
:root {
  --ease-standard: cubic-bezier(.2, 0, 0, 1);
  --ease-enter: cubic-bezier(0, 0, .2, 1);
  --ease-exit: cubic-bezier(.4, 0, 1, 1);
  --ease-emphasized: cubic-bezier(.2, .8, .2, 1);
}
```

## 5.4 Windows hover and press

- Primary button hover: slight gradient brightness increase and subtle shadow.
- Primary pressed: scale 0.985, darken slightly, 80 ms.
- Secondary hover: surface brightens one step.
- Card hover: translate Y −2 px maximum; border brightens.
- Sidebar hover: subtle surface fill.
- Selected sidebar item: persistent accent marker.
- Icon button hover: neutral hit-area surface appears.
- Tooltip: delay approximately 500 ms.
- Focus-visible: 2 px high-contrast ring with offset.
- Disabled: no hover elevation; muted appearance; clear disabled semantics.

Hover must not be confused with selected or keyboard focus.

## 5.5 TV focus and press

TV has no hover. Use:

- Focused: scale 1.03–1.05; 2–3 dp outline; brighter surface; 140–180 ms.
- Pressed: scale 0.98–0.99 briefly.
- Selected: persistent accent marker/border independent of focus.
- Disabled: reduced emphasis and skipped in directional navigation where appropriate.

Ensure scale does not cause clipping or collisions.

## 5.6 Component motion table

| Component | Trigger | Motion | Duration |
|---|---|---|---:|
| Button | Hover | Brightness + subtle shadow | 120 ms |
| Button | Press | Scale 0.985 | 80 ms |
| Card | Hover | Translate Y −2 px | 150 ms |
| Sidebar | Hover | Surface fade | 120 ms |
| Sidebar | Select | Accent marker | 180 ms |
| Tooltip | Show | Fade + Y 4 px | 120 ms |
| Popover | Open | Fade + scale .98 → 1 | 160 ms |
| Dialog | Open | Fade + scale .96 → 1 | 220 ms |
| Dialog | Close | Fade + scale 1 → .98 | 140 ms |
| Toast | Enter | Fade + Y 8 px | 180 ms |
| TV focus | Focus | Scale + outline + surface | 160 ms |
| TV dialog | Open | Fade + slight scale | 220 ms |
| Connection state | Change | Status crossfade | 180 ms |
| Pairing code | Refresh | Digit crossfade | 160 ms |

## 5.7 Loading and progress

- Spinner for short indeterminate work.
- Progress bar only when progress is measurable.
- Device discovery uses a restrained scan indicator plus text.
- Do not animate skeletons indefinitely.
- Stop animations when a view is hidden.
- Provide timeout and recovery action for long tasks.
- Do not use an animated 3D icon as a spinner.

## 5.8 Connection state machine

```text
idle
  -> discovering
  -> device_available
  -> pairing_required
  -> pairing
  -> connecting
  -> connected
  -> streaming
  -> reconnecting
  -> disconnected
  -> failed
```

Each state requires a user-facing label, semantic status, allowed next action, timeout/retry policy, diagnostic event, and visual treatment.

Never show Connected before the transport and protocol handshake succeeds. Never show Streaming before frames are received and rendered.

## 5.9 Reduced motion

- Remove scale and large translation.
- Use quick opacity transitions.
- Stop decorative motion.
- Preserve focus and state feedback.
- Do not remove essential progress/status communication.

---

# 6. Component specifications

Every component defines anatomy, variants, states, platform behaviour, accessibility, and failure handling.

## 6.1 Buttons

Variants: Primary, Secondary, Tertiary/Ghost, Destructive, Icon-only, TV Primary, TV Secondary.

Sizes:
- Desktop compact: 32 px; non-primary only.
- Desktop standard: 40 px.
- Desktop large: 48 px.
- TV: 64–76 dp depending on context.

Requirements:
- Use action verbs.
- One primary action per visual group.
- Loading prevents duplicate activation.
- Destructive actions require confirmation when impact is significant.
- Icon-only controls require accessible names and desktop tooltips.
- Every button implements default, hover, focus, pressed, disabled, and loading states.

## 6.2 Inputs

Anatomy: label, control, optional icon, helper text, error text.

States: default, hover, focus, filled, invalid, disabled, read-only.

Rules:
- Labels remain visible; placeholders are not labels.
- Error text explains recovery.
- Pairing code supports numeric input and paste.
- Do not auto-submit before full code entry unless designed and tested.
- Never log pairing codes or secrets.

## 6.3 Cards

Variants: Device, Source, Metric, Settings Group, Log Event, Empty State.

- One clear purpose per card.
- Internal padding: 16–20 px desktop; more on TV.
- Avoid unnecessary nested cards.
- Static cards must not look clickable.
- Interactive TV cards must show focus.

## 6.4 Status badges

Ready, Connecting, Connected, Streaming, Warning, Failed, Offline, Unknown.

- Include text.
- Use semantic colours consistently.
- No continuous pulsing.
- Pair colour with iconography or text.

## 6.5 Dialogs

Windows:
- Centered modal for blocking decisions.
- Popover for lightweight controls.
- Escape dismisses when safe.
- Focus enters and returns to trigger.

TV:
- Centered panel or full-screen flow.
- Large actions and visible focus.
- Back dismisses when safe.
- Pairing approval identifies sender and explains the request.
- Never silently approve.

## 6.6 Toasts and notifications

- Short, actionable, non-blocking.
- No more than three stacked.
- Do not use toast for decisions.
- Streaming disconnection is persistent and recoverable, not a fleeting toast.
- TV banners must not obscure video for long.

## 6.7 Empty states

Every empty state explains what is empty, why, and what the user can do.

Examples:
- No devices: “Make sure your TV and PC are on the same network.” Action: “Scan again”.
- No logs: “Logs will appear after AirScreen performs an operation.”
- No paired devices: “Pair a TV to connect more quickly next time.”

## 6.8 Errors

Every error describes what failed in user language, provides recovery, preserves useful context, and keeps raw technical details in diagnostics.

Examples:
- TV not reachable → Retry / Check network.
- Pairing expired → Generate a new code.
- Authentication failed → Pair again.
- Decoder unavailable → View supported formats / Diagnostics.
- Audio unavailable → Continue without audio if supported.

---

# 7. Windows application architecture

## 7.1 Cast dashboard

- Header: “Cast your screen”.
- Selected receiver card.
- Device discovery state.
- Source selector: Entire screen, Window, Application.
- Quality summary.
- Primary Start Streaming action.
- Small connection health summary.

Keep advanced codec settings out of the default dashboard.

## 7.2 Devices

- Available devices.
- Paired devices.
- Scan state.
- Platform and device name.
- Connection state.
- Last seen where available.
- Manual connection if discovery fails.
- Retry/rescan.

Do not expose raw IP by default unless useful; put it in device details.

## 7.3 Pairing

- Explain why pairing is needed.
- Show receiver identity.
- Clear code entry and paste.
- Expiry if provided by protocol.
- Explicit success/rejection/expired states.
- Never store pairing codes in logs.

## 7.4 Active streaming

- Receiver name.
- Streaming state.
- Pause/stop if supported.
- Audio controls if supported.
- Configured resolution and FPS.
- Measured bitrate and latency only when available.
- Connection health and recovery state.
- Preview only if reliable and does not compete with media pipeline.

## 7.5 Settings

Sections:
- General
- Video
- Audio
- Network
- Security
- Advanced
- Diagnostics

Defaults should work for most users. Advanced settings are separated. Each setting has a description and indicates when reconnection is required.

## 7.6 Logs and diagnostics

- Severity and category filters.
- Search.
- Timestamp and summary.
- Expandable technical detail.
- Export.
- Redact keys, tokens, pairing codes, and private content.

---

# 8. Android TV receiver architecture

## 8.1 Ready to Connect

- AirScreen logo.
- “Ready to connect”.
- TV device name.
- Network state.
- Pairing instructions or expiring code when appropriate.
- Short help.
- Optional IP/port under device information.

Do not show a permanent pairing code unless the protocol explicitly supports that security model.

## 8.2 Pairing approval

- Sender name.
- Request explanation.
- Trust context.
- Allow / Deny.
- Expiry/timeout where relevant.
- Explicit user approval; never silently approve.

## 8.3 Streaming

- Fullscreen video.
- Hide controls after inactivity.
- Show controls on input or relevant event.
- Minimal status overlay.
- Deliberate Back behaviour.
- Never terminate on an accidental Back press without clear policy.
- Keep audio state accessible.
- No decorative animated 3D icons over the video.

## 8.4 TV settings

Groups: Connection, Video, Audio, Paired Devices, About, Diagnostics.

Use plain-language values and D-pad-only navigation. Advanced details belong in Diagnostics.

---

# 9. Accessibility and input standards

## 9.1 Windows keyboard

- Tab / Shift+Tab: traverse controls.
- Enter / Space: activate.
- Escape: dismiss safe dialogs/popovers.
- Arrow keys: conventional menu/list navigation.
- Do not steal focus during discovery.
- Focus ring remains visible.

## 9.2 Android TV remote

- D-pad: spatial navigation.
- OK/Enter: activate.
- Back: defined navigation/dismissal.
- Focus restoration after dialogs.
- No focus traps.
- No pointer-only actions.

## 9.3 Accessibility requirements

Target WCAG 2.2 AA principles for desktop and Android accessibility best practices for TV.

- Normal text contrast target 4.5:1.
- Large text contrast target 3:1, per WCAG definitions.
- Control boundaries and focus indicators must be distinguishable.
- Meaningful accessible names.
- Semantic grouping of settings.
- Support text scaling where practical.
- Reduced-motion support.
- Keyboard-only and remote-only operation.
- Test with screen readers and TalkBack.
- Captions/audio accessibility where supported by streaming architecture.

---

# 10. Responsive behaviour

## 10.1 Windows

Test at 100%, 125%, 150%, and 200% scaling.

- Wide ≥1440 px: full sidebar and optional inspector.
- Standard 1120–1439 px: full sidebar; main content may become single-column.
- Compact 960–1119 px: reduce padding; hide non-essential inspector.
- Below minimum: enforce minimum supported window or provide intentional compact mode.

Use native framework window-size classes where available rather than copying web breakpoints blindly.

## 10.2 TV

- 1920 × 1080 reference.
- Responsive constraints, not absolute positioning for everything.
- Validate on actual Sony TV.
- Respect system font scale where possible.
- Prevent focus scale clipping at edges.

---

# 11. Content and microcopy

Tone: clear, calm, direct, technically accurate, never blaming.

Preferred:
- “TV found”
- “Pairing required”
- “Connecting to BRAVIA S25…”
- “Streaming”
- “Connection interrupted”
- “Try again”
- “Check that both devices are on the same network”

Avoid:
- “Oops!!!”
- “Something went wrong” without context.
- “Magic happening…”
- Unverified performance claims.
- Raw protocol errors in primary UI.

Terminology:
- **Sender:** Windows PC.
- **Receiver:** TV.
- **Pair:** establish trust.
- **Connect:** establish current session.
- **Stream:** video/audio data is actively flowing.
- **Disconnect:** terminate current session.

---

# 12. Telemetry and data integrity

| Type | Example |
|---|---|
| Configured | Target resolution: 1920 × 1080 |
| Negotiated | Negotiated codec: H.264 |
| Measured | Current FPS: 58.7 |
| Estimated | Estimated latency: 45 ms |
| Unsupported | Not reported by receiver |

Rules:
- Never present placeholder metrics as real.
- Use “—” or “Not available” when absent.
- Always show units.
- Clarify what latency measures.
- Do not promise 1080p60 until end-to-end tested.
- Throttle telemetry updates to avoid jitter.

---

# 13. Engineering handoff and implementation

## 13.1 Suggested repository structure

```text
design-system/
  README.md
  tokens/
    primitives.json
    semantic.json
    motion.json
    typography.json
  specs/
    components/
    windows/
    android-tv/
  assets/
    brand/
    icons-3d/
      source/
      exports/
      manifest.json
```

## 13.2 CSS token example

```css
:root {
  color-scheme: dark;
  --as-brand-primary: #8057FF;
  --as-brand-primary-hover: #916EFF;
  --as-bg-canvas: #080B16;
  --as-bg-sidebar: #0D1222;
  --as-bg-surface: #11182A;
  --as-bg-raised: #171F34;
  --as-text-primary: #F7F8FC;
  --as-text-secondary: #B3BDD0;
  --as-text-tertiary: #8491AA;
  --as-border-subtle: rgba(255,255,255,.05);
  --as-border-default: rgba(255,255,255,.08);
  --as-radius-sm: 8px;
  --as-radius-md: 12px;
  --as-radius-lg: 16px;
  --as-radius-xl: 20px;
  --as-space-1: 4px;
  --as-space-2: 8px;
  --as-space-3: 12px;
  --as-space-4: 16px;
  --as-space-6: 24px;
  --as-space-8: 32px;
  --as-duration-fast: 120ms;
  --as-duration-normal: 180ms;
  --as-duration-medium: 240ms;
  --as-duration-slow: 320ms;
  --as-ease-standard: cubic-bezier(.2, 0, 0, 1);
}
```

## 13.3 Button component contract

A button accepts:
- `variant`
- `size`
- `disabled`
- `loading`
- `iconLeading`
- `iconTrailing`
- `fullWidth`
- `accessibleName`
- `onActivate`

It implements:
- Default, hover, focus-visible, pressed, disabled, loading.
- Keyboard activation.
- Accessible role/name.
- Duplicate-activation prevention while loading.
- Reduced-motion behaviour.
- Stable dimensions across states.

Any icon supplied to a button must be an approved AirScreen 3D icon asset.

## 13.4 Android Compose contract

- Centralised `AirScreenTheme`.
- Colour, typography, shape, and spacing definitions.
- Reusable composables.
- Explicit TV focus handling.
- Focus restoration after dialogs.
- Stable keys in lazy lists.
- State-driven UI.
- No business logic inside visual composables.
- Avoid recomposition-heavy animations.
- Validate on real TV hardware.
- Use the approved 3D icon asset pipeline.

## 13.5 Architecture rules

- UI state derives from application state.
- Connection state has one authoritative owner.
- Telemetry is throttled before rendering.
- Media pipeline work stays off the UI thread.
- Design components do not own protocol/transport logic.
- Use testable state holders and dependency injection where appropriate.
- Keep 3D asset decoding and rendering from blocking startup or streaming.

---

# 14. Quality assurance and definition of done

## 14.1 Visual QA

- Tokens used consistently.
- No one-off colours/radii without justification.
- Typography hierarchy consistent.
- Hover/focus/selected/pressed/disabled states complete.
- No text clipping at supported scaling.
- Focus outline not clipped.
- Contrast verified.
- Loading, empty, error, and success states covered.
- All interface icons use the approved 3D family.
- No flat 2D, outline, sketch, or emoji icons shipped.

## 14.2 Windows QA

- Keyboard-only operation.
- Mouse hover and pressed behaviour.
- Window resizing.
- High-DPI scaling.
- Screen-reader names.
- Discovery while navigating.
- No focus theft.
- No UI freeze during streaming.
- Long names and missing metadata.
- Connection loss and recovery.

## 14.3 TV QA

- Physical remote-only operation.
- D-pad navigation on every screen.
- Focus order and restoration.
- Back behaviour.
- 10-foot readability.
- Safe area/overscan.
- Pairing timeout and denial.
- Stream start/stop.
- Connection loss during playback.
- Audio state.
- Long-running playback without UI degradation.
- 3D icon readability at actual TV density.

## 14.4 Motion QA

- Motion does not block input.
- No hover layout shift.
- No excessive scaling.
- Reduced motion works.
- Animations stop when irrelevant.
- No decorative motion during fullscreen playback.
- TV focus remains responsive.
- 3D icons do not spin, wobble, or pulse continuously.

## 14.5 Definition of done

A screen is complete only when:
- Default state is implemented.
- Hover/focus/pressed/disabled states are implemented.
- Loading and error states are implemented.
- Empty state exists where applicable.
- Keyboard or D-pad navigation is verified.
- Accessibility names and contrast are checked.
- Reduced motion is handled.
- Real-device validation is complete.
- No unverified performance claims are displayed.
- Every icon is an approved 3D asset or intentionally omitted.

---

# 15. Recommended delivery sequence

1. Lock brand mark, palette, typography, and foundations.
2. Define the 3D icon art direction and approve a small pilot set.
3. Produce the core 3D icon family and asset manifest.
4. Implement semantic tokens on both platforms.
5. Build buttons, inputs, cards, status, dialogs, and navigation.
6. Implement Windows shell and Cast dashboard.
7. Implement discovery and pairing flows.
8. Implement active streaming and diagnostics.
9. Implement TV Ready to Connect.
10. Implement TV pairing approval.
11. Implement TV fullscreen streaming.
12. Implement TV settings and diagnostics.
13. Add motion and accessibility refinements.
14. Run visual, interaction, and hardware QA.

Do not commission or generate hundreds of 3D icons before approving a small representative set. First approve navigation, TV, display, network, security, and audio icons. Then scale the family.

---

# 16. Final product standard

AirScreen should feel like a cohesive, premium, dependable wireless display utility.

The Windows experience should be efficient and diagnostic-rich without becoming cluttered. The TV experience should be cinematic and almost invisible once streaming begins. The 3D iconography should make the product recognisable without overwhelming its usability.

**The design system succeeds when users can discover, trust, connect, and stream without needing to understand the underlying protocol—and every visual element feels like it belongs to the same product.**

**End of specification.**
