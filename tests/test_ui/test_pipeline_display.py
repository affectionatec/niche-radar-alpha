"""Tests for PipelineDisplay state parsing and rendering."""

from niche_radar.ui.pipeline_display import PipelineDisplay, PhaseStatus


class TestLogParsing:
    """Verify log messages update internal state correctly."""

    def test_pipeline_init_sets_header(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_run=abc-123 items=245 budget=310")
        assert d.state.run_id == "abc-123"
        assert d.state.total_items == 245
        assert d.state.budget_max == 310

    def test_phase_a_starts_on_items_message(self):
        d = PipelineDisplay(live=False)
        d.log("phase=A items=100")
        assert d.state.phase_a.status == PhaseStatus.RUNNING
        assert d.state.phase_a.total == 100

    def test_phase_a_item_done_increments(self):
        d = PipelineDisplay(live=False)
        d.log("phase=A items=10")
        d.log("phase_a_item=1/10")
        d.log("phase_a_item=2/10")
        assert d.state.phase_a.completed == 2

    def test_a1_pass_increments_counter(self):
        d = PipelineDisplay(live=False)
        d.log("A1=PASS conf=0.95 type=pain_point")
        assert d.state.a1_passed == 1

    def test_a1_reject_increments_counter(self):
        d = PipelineDisplay(live=False)
        d.log("A1=REJECT type=noise reason='not actionable'")
        assert d.state.a1_rejected == 1

    def test_a2_done_increments_counter(self):
        d = PipelineDisplay(live=False)
        d.log("A2=DONE")
        assert d.state.a2_done == 1

    def test_phase_a_done(self):
        d = PipelineDisplay(live=False)
        d.log("phase=A items=100")
        d.log("phase=A done passed=80 rejected=20")
        assert d.state.phase_a.status == PhaseStatus.DONE
        assert d.state.a1_passed == 80
        assert d.state.a1_rejected == 20

    def test_phase_b_running(self):
        d = PipelineDisplay(live=False)
        d.log("phase=B extractions=182")
        assert d.state.phase_b.status == PhaseStatus.RUNNING
        assert d.state.phase_b.total == 182

    def test_phase_b_skip(self):
        d = PipelineDisplay(live=False)
        d.log("phase=B skip empty")
        assert d.state.phase_b.status == PhaseStatus.DONE

    def test_phase_c_running(self):
        d = PipelineDisplay(live=False)
        d.log("phase=C clusters=45")
        assert d.state.phase_c.status == PhaseStatus.RUNNING
        assert d.state.phase_c.total == 45

    def test_cluster_done_increments_phase_c(self):
        d = PipelineDisplay(live=False)
        d.log("phase=C clusters=3")
        d.log("CLUSTER_DONE verdict=GO score=62/70 feasibility=0.85")
        d.log("CLUSTER_DONE verdict=NO-GO score=30/70 feasibility=0.4")
        assert d.state.phase_c.completed == 2
        assert d.state.verdicts["GO"] == 1
        assert d.state.verdicts["NO-GO"] == 1

    def test_phase_c_done(self):
        d = PipelineDisplay(live=False)
        d.log("phase=C clusters=1")
        d.log("phase=C done")
        assert d.state.phase_c.status == PhaseStatus.DONE

    def test_phase_d_running(self):
        d = PipelineDisplay(live=False)
        d.log("phase=D persisting 12 clusters")
        assert d.state.phase_d.status == PhaseStatus.RUNNING
        assert d.state.phase_d.total == 12

    def test_phase_d_cluster_persist_increments(self):
        d = PipelineDisplay(live=False)
        d.log("phase=D persisting 2 clusters")
        d.log("cluster=abc12345 verdict=GO score=65/70 tier=hot niche=ai-writing")
        assert d.state.phase_d.completed == 1
        assert d.state.niches_persisted == ["ai-writing"]

    def test_pipeline_done(self):
        d = PipelineDisplay(live=False)
        d.log("phase=A items=10")
        d.log("pipeline_done {'pipeline_run': 'x', 'items': 10}")
        assert d.state.phase_a.status == PhaseStatus.DONE
        assert d.state.finished is True

    def test_pipeline_aborted(self):
        d = PipelineDisplay(live=False)
        d.log("phase=A items=10")
        d.log("pipeline_aborted reason=budget_exceeded")
        assert d.state.aborted is True

    def test_budget_tracking(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_run=x items=5 budget=100")
        d.log("A1=PASS conf=0.9 type=pain_point")
        d.log("A1=PASS conf=0.8 type=pain_point")
        d.log("A2=DONE")
        assert d.state.budget_used == 3

    def test_activity_log_captures_messages(self):
        d = PipelineDisplay(live=False)
        d.log("A1=PASS conf=0.95 type=pain_point")
        d.log("A1=REJECT type=noise reason='spam'")
        assert len(d.state.activity) == 2

    def test_activity_log_max_size(self):
        d = PipelineDisplay(live=False)
        for i in range(20):
            d.log(f"A1=PASS conf=0.{i} type=pain_point")
        assert len(d.state.activity) == 12

    def test_pipeline_skipped_no_items(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_skipped reason=no_items")
        assert d.state.finished is True

    def test_phase_c_per_cluster_progress(self):
        d = PipelineDisplay(live=False)
        d.log("phase=C clusters=2")
        d.log("phase_c_cluster=1/2")
        d.log("phase_c_cluster=2/2")
        assert d.state.phase_c.completed == 2

    def test_phase_d_dry_run(self):
        d = PipelineDisplay(live=False)
        d.log("phase=D dry_run skipping 5 clusters")
        assert d.state.phase_d.status == PhaseStatus.DONE


class TestRendering:
    """Verify the layout renders without errors in various states."""

    def test_render_initial_state(self):
        d = PipelineDisplay(live=False)
        renderable = d._build_layout()
        assert renderable is not None

    def test_render_mid_phase_a(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_run=test items=50 budget=200")
        d.log("phase=A items=50")
        d.log("A1=PASS conf=0.9 type=pain_point")
        d.log("phase_a_item=1/50")
        renderable = d._build_layout()
        assert renderable is not None

    def test_render_all_done(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_run=test items=10 budget=100")
        d.log("phase=A items=10")
        d.log("phase=A done passed=8 rejected=2")
        d.log("phase=B extractions=8")
        d.log("phase=C clusters=3")
        d.log("phase=C done")
        d.log("phase=D persisting 2 clusters")
        d.log("pipeline_done {}")
        renderable = d._build_layout()
        assert renderable is not None

    def test_render_aborted(self):
        d = PipelineDisplay(live=False)
        d.log("pipeline_run=test items=10 budget=5")
        d.log("phase=A items=10")
        d.log("pipeline_aborted reason=budget_exceeded")
        renderable = d._build_layout()
        assert renderable is not None

    def test_context_manager_no_crash(self):
        d = PipelineDisplay(live=False)
        with d:
            d.log("pipeline_run=test items=5 budget=50")
            d.log("phase=A items=5")
            d.log("pipeline_done {}")


class TestCLIIntegration:
    """Verify --no-tui flag and auto-detect logic."""

    def test_no_tui_flag_parsed(self):
        from niche_radar.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze", "--no-tui"])
        assert args.no_tui is True

    def test_no_tui_flag_default(self):
        from niche_radar.__main__ import build_parser

        parser = build_parser()
        args = parser.parse_args(["analyze"])
        assert args.no_tui is False
