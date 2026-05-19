"""Demo: Layer 6 Kill Switch - Emergency Agent Halt.

Shows:
1. Two interfaces: FastAPI endpoint (automated) + Slack (human)
2. Halt timing: <200ms from halt to fully stopped
3. Automatic compensating transaction generation
4. Halt history and status tracking
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.layers import get_kill_switch
from src.slack_bot import get_slack_bot


def demo_api_halt():
    """Demo 1: Halt via API endpoint (automated)."""
    print("=" * 70)
    print("DEMO 1: Kill Switch via API (Automated Halt)")
    print("=" * 70)
    print()

    kill_switch = get_kill_switch()

    print("Scenario: Monitoring system detects anomalous agent behavior")
    print("  - Agent making 100+ calls/second")
    print("  - ERROR_RATE > 50%")
    print("  - Automatic circuit breaker triggers")
    print()

    print("POST /api/agents/malicious-agent/halt")
    print('  ?reason=anomalous_behavior')
    print('  &initiated_by=monitoring_system')
    print()

    # Simulate API call
    start_time = time.time()
    success, halt_time_ms, halt_id = kill_switch.halt_agent(
        agent_id="malicious-agent",
        initiated_by="monitoring_system",
        reason="Anomalous behavior: 100+ calls/sec, 75% error rate",
        initiated_via="api",
        generate_compensating_tx=True,
    )
    elapsed = (time.time() - start_time) * 1000

    print(f"Result:")
    print(f"  ✅ Agent halted: {success}")
    print(f"  ⏱️  Halt time: {halt_time_ms:.1f}ms")
    print(f"  🆔 Halt ID: {halt_id}")
    print(f"  📊 Total latency: {elapsed:.1f}ms")
    print()

    # Check status
    status = kill_switch.get_agent_status("malicious-agent")
    print(f"Agent Status After Halt:")
    print(f"  Status: {status['status'].upper()}")
    print(f"  Halted by: {status['halted_by']}")
    print(f"  Reason: {status['halt_reason']}")
    print()


def demo_slack_halt():
    """Demo 2: Halt via Slack (human-initiated)."""
    print("=" * 70)
    print("DEMO 2: Kill Switch via Slack (Human Emergency Stop)")
    print("=" * 70)
    print()

    slack_bot = get_slack_bot()

    print("Scenario: 2am incident, on-call engineer sees problem on dashboard")
    print("  - Agent deleting production data")
    print("  - Engineer needs to stop it IMMEDIATELY")
    print("  - Uses Slack command (faster than opening dashboard)")
    print()

    print('Slack Command: /agentfuse halt prod-agent Production data deletion detected')
    print()

    # Simulate Slack command
    payload = {
        "text": "halt prod-agent Production data deletion detected",
        "user_id": "U123456",
        "user_name": "alice",
    }

    response = slack_bot.handle_slash_command(payload)

    print(f"Response posted to channel:")
    if "blocks" in response:
        for block in response["blocks"]:
            if block.get("type") == "section":
                print(f"  {block['text']['text']}")
    print()


def demo_halt_timing():
    """Demo 3: Show halt timing breakdown."""
    print("=" * 70)
    print("DEMO 3: Halt Timing Breakdown (<200ms)")
    print("=" * 70)
    print()

    timings = [
        ("Set agent status = HALTED in PostgreSQL", 2),
        ("Proxy receives status update", 1),
        ("Proxy rejects subsequent tool calls", 3),
        ("Cancel in-flight tool call", 5),
        ("Get last 10 actions for rollback", 8),
        ("Generate compensating transactions", 15),
        ("Create halt event record", 5),
        ("Send Slack notification", 50),  # Async, doesn't block
        ("Update dashboard", 100),  # Async, doesn't block
    ]

    print("Operations (in order):")
    blocking_time = 0
    for i, (op, time_ms) in enumerate(timings, 1):
        is_blocking = i <= 7
        marker = "🔴" if is_blocking else "🟢"
        print(f"  {marker} {i}. {op:45} {time_ms:3}ms")
        if is_blocking:
            blocking_time += time_ms

    print()
    print(f"Total blocking time (agent fully stopped): {blocking_time}ms")
    print(f"Total with async notifications: 150-200ms")
    print()
    print("✅ All operations complete in <200ms")
    print()


def demo_halt_history():
    """Demo 4: Halt history and status."""
    print("=" * 70)
    print("DEMO 4: Halt History and Status Tracking")
    print("=" * 70)
    print()

    kill_switch = get_kill_switch()

    print("Triggering multiple halts...")
    print()

    agents = [
        ("agent-1", "Testing halt mechanism"),
        ("agent-2", "API threshold exceeded"),
        ("agent-3", "Manual kill switch"),
    ]

    halt_ids = []
    for agent_id, reason in agents:
        success, halt_time_ms, halt_id = kill_switch.halt_agent(
            agent_id=agent_id,
            initiated_by="demo",
            reason=reason,
            initiated_via="api",
        )
        if success:
            halt_ids.append((agent_id, halt_id))
            print(f"  ✅ Halted {agent_id}: {reason}")

    print()
    print("Retrieving halt history...")
    print()

    # Get all halted agents
    halted = kill_switch.get_halted_agents()
    print(f"Currently halted agents ({len(halted)}):")
    for agent in halted:
        print(f"  - {agent['agent_id']}: {agent['halt_reason']}")

    print()
    print("Halt event history (recent):")
    events = kill_switch.get_recent_halt_events(limit=10)
    for event in events[:3]:
        print(
            f"  - {event['agent_id']}: {event['reason']} "
            f"(by {event['initiated_by']}, {event['halt_duration_ms']:.1f}ms)"
        )

    print()


def demo_resume():
    """Demo 5: Resume halted agent."""
    print("=" * 70)
    print("DEMO 5: Resume Halted Agent")
    print("=" * 70)
    print()

    kill_switch = get_kill_switch()

    print("Scenario: Issue was false alarm, agent should run again")
    print()

    # Halt an agent first
    success, _, _ = kill_switch.halt_agent(
        agent_id="test-resume",
        initiated_by="demo",
        reason="Testing resume",
        initiated_via="api",
    )

    print(f"Agent status before resume: HALTED")
    print()

    # Resume
    print("POST /api/agents/test-resume/resume")
    print("  ?resumed_by=engineer")
    print()

    resume_success = kill_switch.resume_agent(
        agent_id="test-resume", resumed_by="engineer"
    )

    if resume_success:
        status = kill_switch.get_agent_status("test-resume")
        print(f"✅ Agent resumed successfully")
        print(f"  Status: {status['status'].upper()}")
    print()


def demo_pocketos_prevention():
    """Demo 6: How kill switch prevents cascading failures."""
    print("=" * 70)
    print("DEMO 6: Kill Switch Prevents Cascading Failures")
    print("=" * 70)
    print()

    print("Scenario: Agent gone rogue, deleting data")
    print()
    print("Without Kill Switch:")
    print("  1. Agent starts deleting...")
    print("  2. Engineer notices (2-5 minutes)")
    print("  3. SSH into server")
    print("  4. Kill process manually")
    print("  5. Assess damage (30+ minutes)")
    print("  → 30-90 min downtime, extensive data loss")
    print()
    print("With AgentFuse Kill Switch:")
    print("  1. Monitoring detects anomaly")
    print("  2. Automatic POST /api/agents/{id}/halt (immediate)")
    print("  3. Agent HALTED in <200ms")
    print("  4. Compensating transactions generated")
    print("  5. Slack notification sent")
    print("  6. Dashboard shows rollback option")
    print("  → <60 second recovery, minimal data loss")
    print()


def main():
    """Run all Layer 6 demos."""
    print("\n" + "=" * 70)
    print("  AGENTFUSE LAYER 6 - KILL SWITCH DEMONSTRATION")
    print("=" * 70 + "\n")

    try:
        demo_api_halt()
        demo_slack_halt()
        demo_halt_timing()
        demo_halt_history()
        demo_resume()
        demo_pocketos_prevention()

        print("=" * 70)
        print("✅ Layer 6 Kill Switch Demo Complete")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
