"""picogame_story.Story: story data from game.json interpreted through the Director.

Semantics are those of the editor's former compileZoneBody (say variants first-match, ask with
set/done/yes/no, goto with if/denied, script -> story.py), plus the per-level effects replay."""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import os
import types

import picogame as pg
import picogame_scene
import picogame_script
import picogame_story
import terminalio

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
GAME = os.path.join(FIX, "quest_game.json")


class FakeButtons:
    A, B = 1, 2

    def __init__(self):
        self._just = 0

    def press(self, mask):
        self._just = mask

    def just_pressed(self, mask):
        return bool(self._just & mask)

    def clear(self):
        self._just = 0


class Rig:
    """A game, a Director on the start level and a Story - plus a driver that presses buttons."""
    def __init__(self, module=None):
        self.game = picogame_scene.Game(pg, GAME)
        self.view = self.game.load()
        self.btn = FakeButtons()
        self.d = picogame_script.Director(pg, self.view.scene, self.btn, terminalio.FONT)
        self.story = picogame_story.Story(self.d, self.game, module)
        self.story.effects(self.view)
        self.shown = []
        box = self.d._ensure_box()
        orig = box.show

        def show(lines):
            self.shown.append(list(lines))
            return orig(lines)
        box.show = show

    def zone(self, tag):
        for z in self.view.zones:
            if z[0] == tag:
                return z
        raise KeyError(tag)

    def run(self, data, answers=(), limit=50):
        """Start the zone data and drive it to the end, answering each box with A (or B)."""
        assert self.d.start(data), "the script must start"
        answers = list(answers)
        for _ in range(limit):
            self.btn.clear()
            if not self.d.tick():
                return
            if self.d.pending:
                return                     # travel requested: the loop would load a level here
            # a box is waiting: answer it
            self.btn.press(self.btn.B if answers and answers[0] == "B" else self.btn.A)
            if answers:
                answers.pop(0)
            if not self.d.tick():
                return
        raise AssertionError("script did not finish")


def test_say_picks_the_first_matching_variant():
    r = Rig()
    r.run(r.zone("elder")[5])
    assert r.shown[-1] == ["Elder:", "Pull the lever."]
    r.d.set("gate_open")
    r.run(r.zone("elder")[5])
    assert r.shown[-1] == ["Elder:", "Go on."]


def test_ask_sets_the_flag_replays_effects_and_is_one_shot():
    r = Rig()
    v = r.view
    assert v.tilemap.get_tile(6, 2) == 7 and v.is_solid(6, 2)
    assert v.named["gate_npc"].visible
    r.run(r.zone("lever")[5], answers=["A"])
    assert r.d.ev("gate_open")
    assert v.tilemap.get_tile(6, 2) == 0, "effects: swap 7 -> 0 must run the moment the flag is set"
    assert not v.is_solid(6, 2), "effects: unsolid"
    assert not v.named["gate_npc"].visible, "effects: hide"
    r.run(r.zone("lever")[5])
    assert r.shown[-1] == ["Already pulled."]


def test_ask_answered_with_b_sets_nothing():
    r = Rig()
    r.run(r.zone("lever")[5], answers=["B"])
    assert not r.d.ev("gate_open")


def test_goto_is_denied_until_the_flag_then_requests_travel():
    r = Rig()
    r.run(r.zone("exit")[5])
    assert r.shown[-1] == ["The gate is shut."]
    assert r.d.pending is None
    r.d.set("gate_open")
    r.run(r.zone("exit")[5])
    assert r.d.pending == ("cave", "entry")


def test_script_zone_runs_story_py_or_a_visible_stub():
    story = types.ModuleType("story")
    calls = []

    def boss_fight(d):
        calls.append("boss")
        yield from d.text(["Boss!"])
    story.boss_fight = boss_fight
    r = Rig(story)
    r.run(r.zone("boss")[5])
    assert calls == ["boss"] and r.shown[-1] == ["Boss!"]
    r2 = Rig(None)
    r2.run(r2.zone("boss")[5])
    assert "no def boss_fight(d)" in r2.shown[-1][0]


def test_enter_is_edge_latched():
    r = Rig()
    started = r.story.enter(r.view, 20, 20)          # inside "elder"
    assert started and r.d.active
    r.run  # noqa: B018  (drive it to the end below)
    for _ in range(10):
        r.btn.press(r.btn.A)
        if not r.d.tick():
            break
    assert not r.story.enter(r.view, 21, 21), "still inside the same zone: no restart"
    assert not r.story.enter(r.view, 200, 200), "outside: nothing"
    assert r.story.enter(r.view, 20, 20), "re-entering starts it again"


def test_director_without_story_refuses_zone_data():
    v = picogame_scene.Game(pg, GAME).load()
    d = picogame_script.Director(pg, v.scene, FakeButtons(), terminalio.FONT)
    try:
        d.start({"say": ["x"]})
    except TypeError:
        return
    raise AssertionError("dict scripts need picogame_story")
