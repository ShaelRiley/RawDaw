"""Rebuild the authored CC0 harmony bank; inventory is curated, not permuted.

Each row chooses a musical gesture and its harmonic rhythm. Shared mode-derived
templates are merged by musical identity, never counted once per key or mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prde1.contracts import canonical_bytes
from prde1.music import MODES
from prde1.progression_bank import DATA, FORMAT, VERSION, equivalence_signature, validate_entry


GROUPS = [
('degrees', 'Pop', ['major'], '''
Open road | 1 5 6 4 | Chorus | A familiar rising-and-returning four-chord loop.
Warm return | 1 6 4 5 | Verse | Gentle movement away from home, then a clear return.
Lift and land | 6 4 1 5 | Chorus | Start on the softer sixth degree and open into the tonic.
Steady horizon | 1 4 6 5 | Chorus | A bright opening with a softer third bar.
Wide circle | 1 6 2 5 | Verse | A connected sixth-to-second turn into the dominant.
Sunrise turn | 4 1 5 6 | Chorus | Begin away from home for an open, repeating chorus.
Gentle question | 1 5 4 5 | Verse | A simple back-and-forth ending on a question.
Home and away | 1 4 1 5 | Verse | Alternate the tonic with departure and anticipation.
Three steps home | 1 4 5 1 | Ending | A direct departure, tension and resolution.
Long way back | 1 3 4 5 | Prechorus | Step outward gradually before the next section.
Soft descent | 1 3 6 4 | Verse | Move through related chords without a hard cadence.
Through the middle | 1 2 4 5 | Prechorus | A steady build toward a dominant landing.
Rising bridge | 4 5 6 3 | Bridge | Rise into the relative minor before changing direction.
Answering chorus | 4 5 1 6 | Chorus | A fourth-degree opening that lands on home midway.
Side-door return | 2 4 1 5 | Verse | Begin on the second degree for a less direct opening.
Connected corners | 2 5 1 6 | Verse | A cadence followed by a gentle sixth-degree turnaround.
Waiting room | 6 2 5 1 | Ending | Related minor movement resolves clearly to home.
Late landing | 4 2 5 1 | Ending | Hold the tonic until the end of the phrase.
Turning pages | 1 6 3 4 | Verse | A calm loop through related harmony.
Minor detour | 1 3 6 2 | Bridge | Move toward the minor side without a final dominant.
Upward invitation | 2 3 4 5 | Prechorus | Consecutive roots create a clear upward build.
Homeward stairs | 6 5 4 1 | Ending | Descending roots relax into a tonic landing.
Reverse stairs | 1 4 5 6 | Chorus | An open ending that leads naturally into another repeat.
Soft question | 6 4 2 5 | Prechorus | Related minor chords lead to a dominant handoff.
Double home | 1:2 4 5 | Verse | Hold home for two measures before moving.
Long homecoming | 1 4 5 1:2 | Ending | Give the final tonic an extra measure of space.
Suspended horizon | 1:2 6 4 | Verse | A spacious tonic followed by a soft two-chord turn.
Quick turnaround | 1:2 4:1/2 5:1/2 1 | Chorus | Two quick changes connect the held opening to home.
Half-bar lift | 1 5 6:1/2 4:1/2 5 | Prechorus | Accelerate the harmonic rhythm near the end.
Two-bar breathing | 1:2 5:2 6:2 4:2 | Verse | A spacious eight-measure version of a four-chord family.
Slow warm return | 1:2 6:2 4:2 5:2 | Verse | Leave room for melody over each harmony.
Short bright loop | 1:1/2 4:1/2 5:1/2 1:1/2 | Chorus | A compact two-measure cadence with fast movement.
Tonic resting place | 1:4 | Intro | Four measures of home for a rhythmic or melodic opening.
Quiet two-chord loop | 1:2 4:2 | Verse | Wide space for a melody over tonic and fourth degree.
Dominant waiting | 1:3 5 | Intro | Keep the first three measures grounded; turn on the last.
Final doorway | 4 5 1:2 | Ending | Three chords fill a complete four-measure phrase.
'''),
('degrees', 'Minor', ['natural_minor', 'dorian', 'harmonic_minor', 'melodic_minor_ascending'], '''
Nightfall circle | 1 6 3 7 | Verse | Minor home moves through its brighter related chords.
Descending night | 1 7 6 5 | Verse | A four-step descent; the fifth follows the chosen mode.
Open minor sky | 1 6 7 1 | Chorus | A broad return through the sixth and seventh degrees.
Quiet minor answer | 1 4 7 3 | Verse | A minor opening reaches its relative-major landing.
Minor bloom | 6 7 1 1 | Chorus | Approach minor home from below, then let it breathe.
Unfinished night | 1 3 7 6 | Verse | A soft loop that avoids a final dominant cadence.
Minor crossroad | 1 4 6 7 | Prechorus | Depart through the fourth degree and build from below.
Round midnight steps | 1 7 4 6 | Bridge | Change the direction of a descending minor phrase.
Shadow and light | 3 7 1 6 | Chorus | Begin on the brighter third before returning to minor home.
Low lantern | 1 6 4 5 | Verse | A sixth-degree opening into a fourth-to-fifth turn.
Descending answer | 6 5 4 1 | Ending | Step back toward the tonic for a settled ending.
Minor preparation | 4 6 7 1 | Ending | Build the return from the fourth, sixth and seventh.
Across the dark | 1 3 4 7 | Bridge | A tonic-to-third change leads into an open modal ending.
Minor long circle | 1 4 7 3 6 2 5 1 | Verse | An eight-chord circle that finally returns home.
Patient nightfall | 1:2 6 7 | Verse | Two measures of minor home before an upward return.
Held minor landing | 1 6 7 1:2 | Ending | Give the final minor chord extra space.
Long descending night | 1:2 7:2 6:2 5:2 | Verse | Let each step of the descent occupy two measures.
Quick minor pulse | 1:1/2 6:1/2 7 1:2 | Chorus | Start with quick changes and settle on the tonic.
Minor doorway | 4 5 1:2 | Ending | A mode-following minor cadence over four measures.
Night and return | 1 6 3 7 1 4 5 1 | Chorus | An open first half becomes a returning second half.
Two minor questions | 1 4 1 7 6 4 5 5 | Prechorus | Two departures set up a longer dominant handoff.
Walking home slowly | 1:2 7 6 4 5 1:2 | Ending | A descending middle gives way to a sustained return.
Soft minor bridge | 6:2 4 1 3:2 7:2 | Bridge | Related chords offer contrast to a tonic-led verse.
'''),
('degrees', 'Pop', ['major', 'natural_minor'], '''
Verse to chorus | 1 5 6 4 1 2 4 5 | Verse | An open four-chord idea gains a stronger handoff.
Returning refrain | 1 6 4 5 1 6 2 5 | Chorus | Repeat an identity with a different final approach.
Eight-bar answer | 1 4 1 5 6 4 5 1 | Chorus | A question in the first half resolves in the second.
Broad homecoming | 1 5 1 3 2 4 1:2 | Ending | A seven-chord phrase with a two-measure final tonic.
Middle lift | 1 3 6 4 2 5 1:2 | Chorus | Related chords connect into a final cadence.
Call and answer | 1 4 5 5 1 4 5 1 | Verse | The first phrase waits; the second completes the thought.
Late chorus lift | 1:2 6:2 4 2 5:2 | Prechorus | The harmony gathers pace before a two-measure handoff.
Wide eight-bar loop | 1:2 4:2 6:2 5:2 | Chorus | Four chords leave plenty of room for a repeating hook.
Descending eight | 1 5 6 3 4 1 2 5 | Verse | A connected descent ends ready to repeat.
Bridge from the fourth | 4 1 2 5 4 6 5:2 | Bridge | A fourth-led contrast avoids an early final landing.
Verse with a doorway | 1 6 3 4 1 6 2 5 | Verse | Keep the opening shape but strengthen the turnaround.
Open then closed | 1 4 5 6 2 5 1:2 | Chorus | A softer first landing is followed by a complete return.
Six-degree answer | 6 4 1 5 6 2 5 1 | Chorus | A familiar identity gets a resolving second phrase.
Twelve-bar pop stroll | 1:2 6:2 4:2 5:2 2 5 1:2 | Verse | Spacious opening changes lead into a quicker closing cadence.
Long refrain | 1:2 5:2 6:2 4:2 1:2 2:2 4 5 1:2 | Chorus | A sixteen-measure loop that ends with a firm tonic landing.
Four-chord hold and turn | 1:3 6 4:3 5 | Verse | Long held chords alternate with one-measure transitions.
'''),
('degrees', 'Cadence', list(MODES), '''
Home return | 1 5 1:2 | Ending | Depart briefly and give home two measures.
Gentle plagal close | 1:2 4 1 | Ending | A fourth-to-tonic ending without a dominant turn.
Second-degree approach | 2 5 1:2 | Ending | A direct second-to-fifth-to-tonic cadence.
Fourth-degree approach | 4:2 5 1 | Ending | Hold the fourth degree before a short dominant return.
Cadence with a detour | 2 5 6 4 | Bridge | The expected tonic becomes a sixth-degree landing.
Long dominant question | 1 4 5:2 | Prechorus | End the phrase by waiting on the fifth degree.
Stepping up to home | 3 4 5 1 | Ending | Ascending roots lead to a final tonic.
Fifth-degree doorway | 5:2 1:2 | Intro | Begin with anticipation and arrive at home halfway.
Two soft landings | 4 1 4 1 | Ending | A repeating plagal gesture suits an unhurried close.
Last-bar cadence | 1:3 4:1/2 5:1/2 | Prechorus | Keep home steady until a quick final-measure turn.
Held closing tonic | 2:1/2 5:1/2 1:3 | Ending | Put the movement up front, then let the final chord ring.
Question with space | 1 2 5:2 | Prechorus | A second-degree departure prepares a held dominant.
Circle to the doorway | 3 6 2 5 | Prechorus | Related roots lead toward a dominant handoff.
Full circle landing | 3 6 2 5 1:4 | Ending | A four-step approach resolves to a four-measure tonic.
Plagal afterthought | 2 5 1 4 1:4 | Ending | Add a gentle fourth-degree answer after the main cadence.
Repeated home question | 1 5 1 5 | Verse | A minimal alternating loop for melodic variation.
'''),
('degrees', 'Dorian', ['dorian'], '''
Dorian light | 1 4 1 7 | Verse | The major fourth degree highlights Dorian's raised sixth.
Dorian lift | 1 3 4 1 | Chorus | A bright fourth-degree chord returns to minor home.
Dorian drift | 1:2 4 7 | Verse | Leave space around the characteristic fourth-degree change.
Dorian conversation | 1 4 2 1 | Verse | Two minor-side chords frame the brighter fourth degree.
Dorian side street | 1 2 4 7 | Bridge | The second degree and fourth offer an open modal turn.
Dorian broad loop | 1:2 4:2 7:2 1:2 | Chorus | A spacious modal loop with a full minor return.
Dorian call | 1 4 1 4 3 7 4 1 | Chorus | Repeat the characteristic shuttle before a longer answer.
Dorian middle ground | 4 2 1 7 | Bridge | Start on the characteristic major fourth for contrast.
Dorian slow answer | 1:3 4 1:3 7 | Verse | Sustained minor chords alternate with short modal colors.
'''),
('degrees', 'Mixolydian', ['mixolydian'], '''
Mixolydian open road | 1 7 4 1 | Chorus | The lowered seventh and major fourth frame the tonic.
Mixolydian back porch | 1 4 7 4 | Verse | An open dominant-mode loop with a plagal flavor.
Mixolydian wide sky | 1:2 7 4 | Verse | A held tonic opens into the characteristic seventh.
Mixolydian refrain | 1 7 1 4 | Chorus | Return to home between modal departures.
Mixolydian climb | 7 4 1:2 | Chorus | Approach home through the seventh and fourth degrees.
Mixolydian side turn | 1 2 7 4 | Bridge | A minor second degree adds contrast to the modal cadence.
Mixolydian soft corner | 1 6 7 4 | Verse | A minor sixth-degree detour softens the major tonic.
Mixolydian answer | 1 7 4 1 6 7 4 1 | Chorus | Repeat a recognizable cadence with a softer second opening.
Mixolydian patient loop | 1:2 7:2 4:2 1:2 | Verse | Eight measures of spacious modal harmony.
'''),
('degrees', 'Lydian', ['lydian'], '''
Lydian window | 1 2 1 5 | Verse | The major second degree exposes Lydian's raised fourth.
Lydian floating | 1:2 2:2 | Verse | A two-chord loop with space around the raised-fourth color.
Lydian shimmer | 1 2 6 5 | Chorus | Bright second-degree harmony meets a softer sixth.
Lydian question | 1 2 3 2 | Bridge | Hover above the tonic rather than making a conventional cadence.
Lydian sunrise | 2 1 5 1 | Chorus | Open on the characteristic major second and return home.
Lydian long horizon | 1:2 2 5 6:2 2 1 | Chorus | A spacious opening leads through the characteristic second.
Lydian echo | 1 2 1 2 6 3 2 1 | Verse | Repeat the main shimmer before a longer return.
Lydian patient question | 1:3 2 5:2 2:2 | Bridge | Held harmony makes room for a floating melody.
'''),
('degrees', 'Phrygian', ['phrygian'], '''
Phrygian close steps | 1 2 1 7 | Verse | The major second degree sits only a semitone above minor home.
Phrygian doorstep | 1:2 2 1 | Verse | A close second-degree departure returns directly to the tonic.
Phrygian descent | 1 7 6 2 | Verse | Descend through related chords into the characteristic second.
Phrygian arch | 1 2 4 1 | Chorus | A close upward step opens into the minor fourth.
Phrygian shadow | 1 6 2 1 | Chorus | The sixth degree leads into the close semitone return.
Phrygian question | 2 1 7 1 | Bridge | Begin with the characteristic chord just above home.
Phrygian wide doorstep | 1:2 2:2 4:2 1:2 | Verse | Let the close modal tension breathe across eight measures.
Phrygian long answer | 1 2 1 7 6 4 2 1 | Chorus | A short modal gesture gains a descending second phrase.
'''),
('degrees', 'Locrian', ['locrian'], '''
Locrian tension field | 1:2 2 3 | Intro | The diminished tonic creates an intentionally unsettled opening.
Locrian close return | 1 2 1 6 | Verse | A close major second contrasts with diminished home.
Locrian darker arch | 1 4 2 1 | Verse | Minor fourth-degree harmony frames the tense tonic.
Locrian side light | 2 3 1 2 | Bridge | More stable neighboring chords contrast with the tonic.
Locrian drifting | 1 6 7 2 | Bridge | An unsettled loop that ends away from home.
Locrian slow return | 1:2 4 2 1:4 | Ending | A long diminished landing is a deliberate color, not a conventional resolution.
'''),
('degrees', 'Harmonic minor', ['harmonic_minor'], '''
Harmonic minor pull | 1 4 5 1 | Ending | The raised seventh gives the fifth degree a major cadence.
Harmonic minor circle | 1 6 2 5 | Verse | A minor loop with a stronger dominant handoff.
Harmonic minor glow | 1 3 6 5 | Bridge | The augmented third-degree chord supplies a distinctive color.
Harmonic minor doorway | 1:2 2 5 | Prechorus | A held tonic leads through diminished second to major fifth.
Harmonic minor spiral | 1 4 7 1 | Verse | The diminished seventh degree pulls back toward home.
Harmonic minor long arc | 1 6 4 2 5:2 1:2 | Chorus | A connected minor phrase ends with a strong return.
Harmonic minor echo | 1 5 1 6 4 2 5 1 | Chorus | A short cadence opens into a longer answer.
Harmonic minor slow turn | 1:3 6 2:2 5:2 | Verse | A slow tonic and sixth precede a two-chord handoff.
'''),
('degrees', 'Melodic minor', ['melodic_minor_ascending'], '''
Melodic minor lift | 1 4 5 1 | Ending | Major fourth and fifth chords brighten the minor tonic.
Melodic minor drift | 1 2 4 1 | Verse | The minor second degree leads toward a bright fourth.
Melodic minor color | 1 3 4 5 | Bridge | An augmented third degree introduces a distinctive transition.
Melodic minor step | 1 2 5 1 | Chorus | Related minor chords lead to the major dominant.
Melodic minor open air | 1:2 4 5 | Prechorus | Minor home opens into two bright one-measure changes.
Melodic minor long lift | 1 2 4 5 1 4 2 5 | Verse | Two related phrases return to a dominant handoff.
Melodic minor soft arc | 1:2 2:2 4:2 1:2 | Chorus | A broad eight-measure modal return.
Melodic minor question | 4 5 2 1 | Bridge | Start with the bright fourth and fifth before a minor answer.
'''),
('chords', 'Soul / jazz', ['major'], '''
Velvet circle | Imaj7 vi7 ii7 V7 | Verse | Seventh chords soften a connected tonic-to-dominant loop.
Soft landing seven | ii7 V7 Imaj7:2 | Ending | A four-measure major seventh cadence.
Open major seven | Imaj7 IVmaj7 ii7 V7 | Verse | Wide major-seventh colors lead into a dominant return.
Gentle seventh axis | Imaj7 V7 vi7 IVmaj7 | Chorus | A familiar four-chord family with richer chord colors.
Late-night return | Imaj7 vi7 IVmaj7 V7 | Verse | A soft sixth and fourth lead to the dominant.
Seventh stairway | iii7 vi7 ii7 V7 | Prechorus | A chain of related seventh chords prepares the tonic.
Seventh open refrain | IVmaj7 V7 iii7 vi7 | Chorus | Begin away from home for a connected open loop.
Seventh home answer | IVmaj7 iii7 ii7 Imaj7 | Ending | Step gently down through related seventh chords.
Sunny secondary turn | Imaj7 VI7 ii7 V7 | Verse | A major sixth-degree dominant adds directed chromatic color.
Second-degree spotlight | Imaj7 II7 ii7 V7 | Bridge | A bright major second contrasts with its minor counterpart.
Third-degree spotlight | Imaj7 III7 vi7 IVmaj7 | Bridge | A secondary dominant points toward the relative minor.
Dominant to dominant | Imaj7 IVmaj7 II7 V7 | Prechorus | A bright second-degree dominant strengthens the handoff.
Two-part soft landing | ii7 V7 Imaj7 vi7 ii7 V7 Imaj7:2 | Chorus | Repeat the cadence with a sixth-degree connecting chord.
Patient seventh landing | ii7:2 V7:2 Imaj7:4 | Ending | An eight-measure cadence with a long final tonic.
Open seventh sky | Imaj7:2 IVmaj7:2 | Verse | A spacious major-seventh shuttle for melody.
Borrowed minor answer | Imaj7 IVmaj7 iv Imaj7 | Ending | Borrow the minor fourth before returning home.
Backdoor seven | Imaj7 IVmaj7 bVII7 Imaj7 | Ending | A lowered-seventh dominant offers an alternative return.
Soft backdoor approach | ii7 iv7 bVII7 Imaj7 | Ending | A borrowed minor fourth prepares the backdoor chord.
Chromatic bridge seven | Imaj7 bIIImaj7 bVImaj7 bVII7 | Bridge | Parallel major-seventh colors create a clear section contrast.
Diminished connector | Imaj7 #i°7 ii7 V7 | Verse | A chromatic diminished passing chord links tonic to second.
Seventh circle complete | Imaj7 IVmaj7 viiø7 III7 vi7 II7 ii7 V7 | Verse | Eight connected seventh chords end ready to repeat.
'''),
('chords', 'Minor / jazz', ['natural_minor', 'harmonic_minor', 'melodic_minor_ascending'], '''
Minor seventh canvas | i7 VImaj7 IIImaj7 VII7 | Verse | Soft minor and major-seventh chords create an open loop.
Minor dominant answer | i7 iv7 V7 i7 | Ending | An authored major dominant returns to the minor tonic.
Minor seventh descent | i7 VII7 VImaj7 V7 | Verse | Descending roots finish on a strong major dominant.
Minor jazz cadence | iiø7 V7 i7:2 | Ending | A half-diminished approach resolves to minor home.
Minor-major landing | iiø7 V7 i(maj7):2 | Ending | A raised-seventh minor tonic keeps a darker final color.
Dark seventh glow | i(maj7) VImaj7 iv7 V7 | Verse | Minor-major-seven harmony contrasts with related chords.
Minor circle seven | i7 iv7 VII7 IIImaj7 VImaj7 iiø7 V7 i7 | Verse | An eight-chord minor circle ends with a directed return.
Slow minor seventh sky | i7:2 VImaj7:2 IIImaj7:2 VII7:2 | Chorus | Eight measures of spacious relative-chord colors.
Minor plagal seven | i7:2 iv7 i7 | Ending | A soft fourth-degree return over four measures.
Minor bright fourth | i7 IV7 i7 VII | Verse | An explicit major fourth brightens a minor seventh tonic.
Borrowed minor bridge | VImaj7 IV7 iiø7 V7 | Bridge | Brighter fourth-degree harmony leads to a minor cadence.
Minor passing diminished | i7 #i°7 iiø7 V7 | Verse | A chromatic connector prepares the half-diminished approach.
'''),
('chords', 'Blues', ['major', 'mixolydian'], '''
Twelve-bar dominant blues | I7:4 IV7:2 I7:2 V7 IV7 I7 V7 | Verse | A twelve-measure blues form with a dominant turnaround.
Quick-change blues | I7 IV7 I7:2 IV7:2 I7:2 V7 IV7 I7 V7 | Verse | Move to the fourth degree in measure two.
Blues final chorus | I7:4 IV7:2 I7:2 V7 IV7 I7:2 | Ending | Close the twelve-measure form on the tonic.
Eight-bar blues turn | I7:2 IV7 I7 V7 IV7 I7 V7 | Verse | A compact eight-measure dominant-chord form.
Dominant porch loop | I7 IV7 I7 V7 | Verse | Three dominant colors in a short recurring loop.
Blues slow question | I7:2 IV7:2 I7:2 V7:2 | Verse | Leave two measures around each change.
Blues bridge climb | IV7 #iv°7 I7 VI7 II7 V7 I7 V7 | Bridge | Chromatic and secondary-dominant movement adds contrast.
Minor twelve-bar blues | i7:4 iv7:2 i7:2 V7 iv7 i7 V7 | Verse | Minor tonic and fourth with an authored major dominant.
Minor blues close | i7:4 iv7:2 i7:2 V7 iv7 i7:2 | Ending | A twelve-measure minor form closes on home.
'''),
('chords', 'Rock / color', ['major', 'mixolydian'], '''
Borrowed rock doorway | I bVII IV I | Chorus | A lowered-seventh major chord leads to a plagal return.
Borrowed bright loop | I bIII IV I | Chorus | A lowered-third major chord supplies parallel-minor color.
Parallel-minor bridge | I bVI bVII I | Bridge | Two borrowed major chords lift back into the tonic.
Plagal minor color | I IV iv I | Ending | Change the fourth from major to minor before home.
Fourth with a shadow | I vi iv V | Verse | A borrowed minor fourth colors the dominant approach.
Bright minor detour | I III vi IV | Bridge | A major third degree points toward the relative minor.
Colorful sixth turn | I VI ii V | Verse | A major sixth degree adds a secondary-dominant color.
Suspended return | Isus2 IVsus2 Vsus4 I | Verse | Open suspensions resolve to an ordinary tonic chord.
Fourth suspension | I IVsus2 Vsus4 I | Chorus | Keep the middle harmonies open before a tonic landing.
Home suspension release | Isus4 I IV V | Intro | Resolve a suspended tonic before moving outward.
Dominant suspension release | I IV Vsus4 V | Prechorus | Delay the dominant's third until the last measure.
Power-chord drive | I5 V5 vi5 IV5 | Chorus | Open fifths outline a familiar four-root loop.
Modal power road | I5 bVII5 IV5 I5 | Chorus | A lowered seventh drives a plagal power-chord return.
Minor power descent | i5 bVII5 bVI5 V5 | Verse | Major-relative roots define the descending power-chord pattern.
First-inversion stroll | I/1 V/1 vi/1 IV/1 | Verse | Prepared first inversions shift the whole-chord voicing.
Inversion homecoming | I IV/1 V/1 I | Ending | Keep the outer chords grounded and soften the middle voicings.
Seventh inversion color | Imaj7/1 vi7/1 ii7/1 V7/1 | Verse | First inversions give a connected seventh-chord loop another register shape.
Passing diminished rise | I #i° ii V | Verse | A diminished chromatic step joins tonic to second degree.
Borrowed slow bridge | I:2 bVI:2 bVII:2 IV:2 | Bridge | Spacious borrowed chords create a broad section contrast.
Sus and return | Isus2:2 Vsus4 I:2 IVsus2:2 V | Chorus | An eight-measure suspended phrase returns to the dominant.
'''),
('chords', 'Modal color', ['dorian'], '''
Dorian seventh light | i7 IV7 i7 VII | Verse | Exact minor seventh and major fourth preserve the Dorian gesture.
Dorian seventh circle | i7 ii7 IV7 i7 | Chorus | Related minor sevenths meet the bright fourth degree.
Dorian suspended arch | i7 IVsus2 VII i7 | Chorus | An open fourth-degree chord broadens the minor return.
'''),
('chords', 'Modal color', ['lydian'], '''
Lydian seventh shimmer | Imaj7 II7 Imaj7 Vmaj7 | Verse | The major second's seventh color emphasizes the raised fourth.
Lydian suspended light | Isus2 II Imaj7 II | Verse | Alternate an open tonic with the characteristic major second.
'''),
('chords', 'Modal color', ['phrygian'], '''
Phrygian seventh doorstep | i7 IImaj7 i7 VII7 | Verse | Exact seventh chords retain the close upper-neighbor root.
Phrygian soft arch | i7 IImaj7 iv7 i7 | Chorus | A close major-seventh departure opens into a minor fourth.
'''),
('chords', 'Modal color', ['locrian'], '''
Locrian half-diminished field | iø7 IImaj7 iii7 iø7 | Verse | The half-diminished tonic is an intentional unsettled color.
Locrian seventh drift | iø7 iv7 VImaj7 IImaj7 | Bridge | Leave the half-diminished tonic for more stable surrounding chords.
'''),
]


def build():
    unique = {}
    for kind, style, modes, text in GROUPS:
        for line in text.strip().splitlines():
            name, source, section, description = [v.strip() for v in line.split('|')]
            entry_modes = modes
            if style == 'Blues' and name.startswith('Minor'):
                entry_modes = ['natural_minor', 'dorian', 'harmonic_minor']
            if name == 'Minor power descent':
                entry_modes = ['natural_minor', 'phrygian', 'harmonic_minor']
            tokens = source.split()
            sequence = ' '.join(t.split(':')[0] for t in tokens)
            durations = [t.split(':')[1] if ':' in t else '1' for t in tokens]
            # Blues/rock flats follow common major-relative notation. Minor/modal
            # authored entries explicitly retain the application's modal basis.
            basis = 'major-relative' if kind == 'chords' and style in ('Soul / jazz', 'Rock / color', 'Blues') else 'mode-relative'
            entry = validate_entry(dict(name=name, style=style, section=section, modes=entry_modes, kind=kind,
                basis=basis, sequence=sequence, durations=durations, durationUnit='bars',
                sourceNotation=sequence, description=description, priority=1 if name in
                ('Open road', 'Warm return', 'Nightfall circle', 'Dorian light', 'Mixolydian open road',
                 'Lydian window', 'Phrygian close steps', 'Locrian tension field', 'Harmonic minor pull', 'Melodic minor lift') else 3,
                credits=[dict(source='Raw Daw authored progression bank', license='CC0-1.0',
                    attribution='Original harmony templates curated for Raw Daw by Shael Riley and contributors',
                    changes='Relative harmony and harmonic-rhythm templates; transposition does not create a new entry')]))
            if entry['id'] in unique:
                current = unique[entry['id']]
                current['modes'] = list(dict.fromkeys(current['modes'] + entry['modes']))
                current['priority'] = min(current['priority'], entry['priority'])
            else:
                unique[entry['id']] = entry
    entries = list(unique.values())
    assert len({equivalence_signature(e) for e in entries}) == len(entries)
    assert sum(e['kind'] == 'degrees' for e in entries) >= len(MODES) * 12
    assert all(any(m in e['modes'] for e in entries) for m in MODES)
    return dict(format=FORMAT, version=VERSION, entries=entries)


if __name__ == '__main__':
    data = build()
    DATA.write_bytes(canonical_bytes(data) + b'\n')
    from collections import Counter
    print(f"{len(data['entries'])} distinct progressions · {dict(Counter(e['kind'] for e in data['entries']))}")
