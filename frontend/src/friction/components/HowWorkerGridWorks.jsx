import { useState } from "react";
import { Server, Layers, Cpu, ArrowDown, ChevronDown, ChevronUp, Info } from "lucide-react";

export function HowWorkerGridWorks({ defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="friction-card how-workergrid-card">
      <div className="how-header" onClick={() => setIsOpen(!isOpen)}>
        <div className="how-title-wrap">
          <Server size={18} className="text-blue" />
          <div>
            <h3 className="how-title">How WorkerGrid Works</h3>
            <div className="subtle">Architecture & Execution Lifecycle of Project Friction Workloads</div>
          </div>
        </div>
        <button type="button" className="ghost-button icon-btn">
          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {isOpen && (
        <div className="how-body">
          <p className="how-intro">
            Project Friction does not perform heavy API collection or analytical calculations inside the main web server thread. 
            Instead, it delegates all work as an asynchronous <strong>DAG workflow</strong> executed by distributed <strong>WorkerGrid Workers</strong>.
          </p>

          <div className="concepts-grid">
            <div className="concept-card">
              <div className="concept-head">
                <Layers size={15} className="text-purple" />
                <strong>1. Task</strong>
              </div>
              <p>Stateful unit of work persisted in PostgreSQL with payload, priority (HIGH/MEDIUM/LOW), retry policy, and dependency requirements.</p>
            </div>

            <div className="concept-card">
              <div className="concept-head">
                <Cpu size={15} className="text-yellow" />
                <strong>2. Queue</strong>
              </div>
              <p>Redis priority queues (high, medium, low) holding ready task IDs for sub-millisecond worker dispatch.</p>
            </div>

            <div className="concept-card">
              <div className="concept-head">
                <Server size={15} className="text-green" />
                <strong>3. Worker</strong>
              </div>
              <p>Autonomous Python process that registers capabilities, emits heartbeats, pops ready tasks from Redis, and executes domain logic.</p>
            </div>
          </div>

          <h4 className="how-subheading">Project Friction 3-Stage Task Lifecycle</h4>

          <div className="diagram-box">
            <div className="diagram-node node-gh">
              <strong>GitHub Repository</strong>
              <div className="subtle">External Data Source</div>
            </div>
            <ArrowDown size={14} className="diagram-arrow" />

            <div className="diagram-node node-pf">
              <strong>1. Project Friction API</strong>
              <div className="subtle">Registers 4-step DAG Workflow in WorkerGrid</div>
            </div>
            <ArrowDown size={14} className="diagram-arrow" />

            <div className="diagram-node node-wg">
              <strong>2. WorkerGrid Redis Task Queue</strong>
              <div className="subtle">HIGH / MEDIUM / LOW Priority Queues</div>
            </div>
            <ArrowDown size={14} className="diagram-arrow" />

            <div className="diagram-stage-container">
              <div className="stage-item">
                <div className="stage-num">3a</div>
                <div className="stage-content">
                  <strong className="mono">friction_collect_github</strong>
                  <p>Worker invokes GitHub REST APIs (PRs, CI runs, Issues) and saves raw JSON snapshots to PostgreSQL.</p>
                </div>
              </div>

              <div className="stage-item">
                <div className="stage-num">3b</div>
                <div className="stage-content">
                  <strong className="mono">friction_calc_metrics</strong>
                  <p>Worker processes raw snapshots into PR review latency, CI failure rate, and backlog staleness metrics.</p>
                </div>
              </div>

              <div className="stage-item">
                <div className="stage-num">3c</div>
                <div className="stage-content">
                  <strong className="mono">friction_generate_report</strong>
                  <p>Worker evaluates indicators against benchmarks, calculates 0-100 friction score, and links evidence items.</p>
                </div>
              </div>
            </div>

            <ArrowDown size={14} className="diagram-arrow" />

            <div className="diagram-node node-ui">
              <strong>4. Project Friction Dashboard</strong>
              <div className="subtle">Renders Scorecard, Indicators, and Drill-down Evidence</div>
            </div>
          </div>

          <div className="how-footer-note">
            <Info size={14} className="text-blue" />
            <span>WorkerGrid autonomous recovery monitor continuously inspects for worker timeouts and re-queues stuck tasks automatically.</span>
          </div>
        </div>
      )}
    </div>
  );
}
