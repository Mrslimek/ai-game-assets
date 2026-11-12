# Character visual notes

Inspected with the Read tool on `assets/qa/characters/knight_views_4x.png` and
`knight_views_overlay_4x.png` and `knight_sheet_annotated_4x.png` and
`anim_frames_4x.png`. Every numeric claim was cross-checked against
`reports/qa_characters.json` and `reports/qa_pixelart.json`.
All observations below were made by directly viewing the rendered sheets.

## Knight views — is it the same character?

- Verdict: theme is consistent (silver plate and red cape and a sword) — identity is NOT preserved.
- Every view has a fully disjoint palette: opaque Jaccard vs knight_front = 0.0 for side and back and three_quarter. View union = 64 opaque colors = 4x16 with zero sharing (119 RGBA counting keying garbage).

Concrete differences by cell of `knight_views_4x.png` (left to right: front / side / back / three_quarter):

- Helmet design: front = pale closed helm with a cross-shaped visor slit. side = silver helm with a RED PLUME on top and no cross. back = plain rounded silver dome (no face side to check). three_quarter = silver helm with a dark slit visor and no plume. At least three distinct helmet designs across four views.
- Visor/face color: front face area is pale with a dark cross slit; side and three_quarter show dark slit visors; back has no face.
- Sword hand flips: front = sword on screen-LEFT pointing down-left. back = screen-LEFT again. side and three_quarter = screen-RIGHT pointing down-right. The knight changes hands between views.
- Sword style: front = thin white blade. side and back = thin white blade with a red grip. three_quarter = short stout white blade. No two match exactly.
- Cape: front = red cape over one shoulder hanging at screen-right. side = large red cape flowing behind at screen-LEFT. back = cape covers the whole torso with a black X strap (unique to the back view). three_quarter = red cape mass at screen-LEFT.
- Lower body: front and side = silver cuisses/greaves with a visible leg gap (front has two fully transparent rows at y=52–53 and its feet are separate 2–7 px components below the gap). back = RED SKIRT/tassets instead of silver legs. three_quarter = silver legs.
- Proportions: silhouette width 35 (front) vs 50 (side) vs 37 (back) vs 49 (three_quarter). Height 50 / 56 / 54 / 51. Baseline 55 / 59 / 58 / 56. Side is +6 px taller and +4 px lower-baselined than front.
- Most common boundary colors differ per view: front #672520FF / side #4D4140FF / back #4C4547FF / three_quarter #611E1AFF.
- Region palettes also disagree: front top third is dominated by reds #9D2F29FF / #631C19FF / #D6342EFF (cape over shoulders) while side and back top thirds are dominated by silver-grey armor tones. The back view's mid third is red (cape torso) where front's mid third is grey/silver with red accents.

Overlay (`knight_views_overlay_4x.png`): the four tinted silhouettes composite into a mushy blob with no shared contour. Head tops misalign by up to ~5 px (side is tallest at h=56). Shoulder lines diverge more. The down-left sword (front/back) and the down-right sword (side/three_quarter) cross at the bottom of the figure. This is a character "set" in theme only.

Head/body split: a convincing neck is detected only in front (neck_y=22; head/body ratio 0.515) and back (neck_y=23; ratio 0.543). side and three_quarter report head_undetected. Side's only upper-zone valley is 22 px wide against a 23 px bulge above it — no real neck. three_quarter's silhouette widens monotonically from helmet to shoulders with no valley at all.

## Animation "frames" — same character?

- Verdict: four independently generated frames of DIFFERENT actions (idle / walk / run / attack) pasted into one 256x64 sheet. Identity drift is expected and confirmed.
- All four frame palettes are disjoint from each other and from every view (opaque Jaccard 0.0 everywhere).
- Concrete differences from `knight_sheet_annotated_4x.png` and `anim_frames_4x.png`:

- idle (w31 h44 base54): helm with a BLACK visor face and two white eye pixels. Small thin white sword held vertical at screen-left with a red hilt. Red cape at screen-right. Legs with a gap and detached foot dashes below it.
- walk (w32 h42 base53): helm with a TAN visible face (open visor) — idle's face is black so the head design differs between frame 1 and frame 2. Larger white sword with a red/orange hilt at screen-left. Cape draped behind. Legs in a stride.
- run (w47 h35 base49): crouched forward-leaning pose. Armor reads BROWNISH instead of silver. Helmet has a RED PLUME (matches the side view's plume; no other frame has one). Weapon is a thin grey horizontal spike pointing screen-left — a lance rather than the vertical sword of the other frames. Huge red cape streaming screen-right. 9 px shorter than idle with a 5 px higher baseline — a different body scale rather than a run cycle of the idle body.
- attack (w32 h47 base54): silver armor and a tan face like walk. A MUCH bigger white sword with a gold crossguard held vertical at screen-left (the blade reaches above the head). Red cape behind. Wide stance. A dark red waist-skirt element not present in idle or walk.

- Frame-to-frame summary of the drift: face color black → tan → plumed → tan. Weapon thin sword → larger sword → horizontal lance → greatsword. Armor silver → silver → brown → silver. Cape size small → medium → huge → large. Body height 44 → 42 → 35 → 47.
- Registration (align centroid-x and baseline-y to frame 1): walk dx=+0.61 dy=+1; run dx=-1.69 dy=+5; attack dx=+3.33 dy=0. Baselines drift up to 5 px and the run frame is 47 px wide vs 31–32 for the others.
- The registered sheet `assets/improved/knight_animation_sheet_registered.png` (verified 256x64 RGBA) equalizes centroids and baselines.
- The x4 GIFs (`knight_sheet_unregistered_x4.gif` / `knight_sheet_registered_x4.gif`; 100 ms per frame; infinite loop) show that registration removes the vertical bounce but the identity flicker remains: face black→tan→plume→tan; weapon sword→sword→lance→greatsword; armor silver→silver→brown→silver.

## Usability verdict

- Views: usable as four independent "knight in pose" portraits. NOT usable as a turntable of one character.
- Sheet: usable only as a four-pose action strip. As animation it will flicker badly. Registration fixes the bounce; nothing fixes identity drift.
- Honesty caveat: "no algorithmic defect" is NOT "production ready". Identity preservation failed at the generation stage and post-processing cannot repair it. Reusing one frame as a base and re-posing (or img2img conditioning on the same init) is the pipeline fix.
