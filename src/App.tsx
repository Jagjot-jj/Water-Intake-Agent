import React, { useState } from 'react';
import {
  Droplets,
  Send,
  RotateCcw,
  Sparkles,
  Bot,
  User,
  CheckCircle2,
  AlertCircle,
  Flame,
  ArrowRight,
  Database,
  Cpu,
  Target
} from 'lucide-react';

interface LogEntry {
  timestamp: string;
  amount_ml: number;
  running_total_ml: number;
}

interface TraceStep {
  step_number: number;
  type: 'plan' | 'tool_call' | 'tool_result' | 'observation' | 'decision';
  description?: string;
  tool?: string;
  arguments?: Record<string, any>;
  result?: Record<string, any>;
}

interface TurnRecord {
  turn_index: number;
  timestamp: string;
  user_message: string;
  plan: string;
  steps: TraceStep[];
  final_response: string;
  intake_at_turn: number;
  goal_at_turn: number;
}

interface MemoryState {
  daily_goal_ml: number;
  today_intake_ml: number;
  logs: LogEntry[];
  history: TurnRecord[];
}

export default function App() {
  // Conversation Memory State (Identical to Python ConversationMemory class)
  const [memory, setMemory] = useState<MemoryState>({
    daily_goal_ml: 2500,
    today_intake_ml: 0,
    logs: [],
    history: []
  });

  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; time: string }>>([
    {
      role: 'assistant',
      content: "Hello! I am your Water Intake Coach AI Agent. I use an autonomous Plan-Act loop with real tool execution (`log_water` and `get_progress`) and conversation memory to help you stay hydrated. How much water did you drink?",
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [latestTrace, setLatestTrace] = useState<TraceStep[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [customGoalInput, setCustomGoalInput] = useState('2500');
  const [showGoalModal, setShowGoalModal] = useState(false);

  // Derived metrics
  const remaining_ml = Math.max(0, memory.daily_goal_ml - memory.today_intake_ml);
  const progress_percent = memory.daily_goal_ml > 0
    ? Math.round((memory.today_intake_ml / memory.daily_goal_ml) * 1000) / 10
    : 0;
  const goal_met = memory.today_intake_ml >= memory.daily_goal_ml;
  const goal_exceeded = memory.today_intake_ml > memory.daily_goal_ml;

  // Real Tool 1: log_water(ml)
  const executeLogWater = (ml: number, currentMem: MemoryState) => {
    if (ml <= 0) {
      return {
        status: 'error',
        error_type: 'negative_or_zero',
        message: `Cannot log ${ml} ml. Amount must be strictly greater than 0 ml.`
      };
    }
    const newTotal = currentMem.today_intake_ml + ml;
    const newRemaining = Math.max(0, currentMem.daily_goal_ml - newTotal);
    const newPercent = Math.round((newTotal / currentMem.daily_goal_ml) * 1000) / 10;

    return {
      status: 'success',
      logged_ml: ml,
      total_ml: newTotal,
      goal_ml: currentMem.daily_goal_ml,
      remaining_ml: newRemaining,
      progress_percent: newPercent,
      goal_met: newTotal >= currentMem.daily_goal_ml,
      goal_exceeded: newTotal > currentMem.daily_goal_ml,
      message: `Logged ${ml} ml. Total today is ${newTotal}/${currentMem.daily_goal_ml} ml (${newPercent}%).`
    };
  };

  // Real Tool 2: get_progress()
  const executeGetProgress = (currentMem: MemoryState) => {
    const total = currentMem.today_intake_ml;
    const goal = currentMem.daily_goal_ml;
    const remaining = Math.max(0, goal - total);
    const percent = Math.round((total / goal) * 1000) / 10;

    return {
      status: 'success',
      today_intake_ml: total,
      daily_goal_ml: goal,
      remaining_ml: remaining,
      progress_percent: percent,
      goal_met: total >= goal,
      goal_exceeded: total > goal,
      date: new Date().toISOString().split('T')[0],
      log_count: currentMem.logs.length
    };
  };

  // Autonomous Agent Plan-Act-Observe-Decide Loop
  const handleAgentRun = (userText: string) => {
    if (!userText.trim() || isProcessing) return;

    setIsProcessing(true);
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Append user message
    setMessages(prev => [...prev, { role: 'user', content: userText, time: timeStr }]);
    setInputMessage('');

    setTimeout(async () => {
      let currentMem = { ...memory };
      const trace: TraceStep[] = [];
      const userLower = userText.toLowerCase().trim();

      // Step 1: PLAN
      const planDesc = `Analyzed user input: "${userText}". Formulating tool calling sequence.`;
      trace.push({
        step_number: 1,
        type: 'plan',
        description: planDesc
      });

      let finalResponse = '';

      // Check if user is updating goal
      const goalMatch = userLower.match(/(?:goal|target)\s*(?:is|to|=|set to)?\s*(\d+)\s*(?:ml)?/);
      if (userLower.includes('goal') && goalMatch && !userLower.includes('drank') && !userLower.includes('had')) {
        const newGoal = parseInt(goalMatch[1], 10);
        trace.push({
          step_number: 2,
          type: 'tool_call',
          tool: 'set_daily_goal',
          arguments: { ml: newGoal }
        });
        currentMem.daily_goal_ml = newGoal;
        const res = executeGetProgress(currentMem);
        trace.push({
          step_number: 3,
          type: 'tool_result',
          tool: 'set_daily_goal',
          result: { status: 'success', new_goal_ml: newGoal, ...res }
        });
        trace.push({
          step_number: 4,
          type: 'decision',
          description: `Updated daily goal to ${newGoal} ml. Re-calibrated hydration progress.`
        });
        finalResponse = `I've updated your daily water intake goal to ${newGoal} ml. You currently have ${res.today_intake_ml} ml logged today (${res.remaining_ml} ml remaining, ${res.progress_percent}% completed).`;
      } else {
        // Detect logging intent
        const numbersFound = userLower.match(/\b\d+\b/g);
        const hasLogIntent = /(?:drank|had|logged|add|plus|another|consumed|drinking|bottle|glass|cup|ml)/.test(userLower) || numbersFound;
        let amountToLog: number | null = null;

        if (hasLogIntent && numbersFound) {
          for (const n of numbersFound) {
            const val = parseInt(n, 10);
            if (val >= 10 && val <= 5000) {
              amountToLog = val;
              break;
            }
          }
        }

        if (amountToLog !== null) {
          // Act: Step 2 -> Tool Call log_water
          trace.push({
            step_number: 2,
            type: 'tool_call',
            tool: 'log_water',
            arguments: { ml: amountToLog }
          });

          const logRes = executeLogWater(amountToLog, currentMem);
          trace.push({
            step_number: 3,
            type: 'tool_result',
            tool: 'log_water',
            result: logRes
          });

          // Update memory with log
          currentMem.today_intake_ml = logRes.total_ml;
          currentMem.logs = [
            ...currentMem.logs,
            {
              timestamp: new Date().toISOString(),
              amount_ml: amountToLog,
              running_total_ml: logRes.total_ml
            }
          ];

          // Act: Step 3 -> Tool Call get_progress
          trace.push({
            step_number: 4,
            type: 'tool_call',
            tool: 'get_progress',
            arguments: {}
          });

          const progressRes = executeGetProgress(currentMem);
          trace.push({
            step_number: 5,
            type: 'tool_result',
            tool: 'get_progress',
            result: progressRes
          });

          // Step 6 -> Observation & Decision
          const total = progressRes.today_intake_ml;
          const goal = progressRes.daily_goal_ml;
          const remaining = progressRes.remaining_ml;
          const percent = progressRes.progress_percent;

          let decisionDesc = '';
          if (progressRes.goal_exceeded) {
            decisionDesc = `Goal exceeded (${total}/${goal} ml). Provide positive reinforcement and remind to maintain balanced hydration.`;
            finalResponse = `Great job! You've logged ${amountToLog} ml, bringing today's total to ${total} ml (${percent}% of your ${goal} ml goal). Goal surpassed! Remember to keep hydration balanced.`;
          } else if (progressRes.goal_met) {
            decisionDesc = `Goal reached (${total}/${goal} ml). Celebrate milestone completion.`;
            finalResponse = `Congratulations! That ${amountToLog} ml brings you to exactly ${total} ml (100% of your ${goal} ml goal). You've successfully hit your hydration target for today!`;
          } else if (remaining <= 400) {
            decisionDesc = `Very close to target (${remaining} ml left). Provide gentle small nudge.`;
            finalResponse = `I've logged your ${amountToLog} ml. You're almost there with ${total} ml recorded today—only ${remaining} ml remaining to hit your ${goal} ml goal (${percent}% completed)!`;
          } else {
            decisionDesc = `Hydration in progress (${remaining} ml remaining). Provide status update.`;
            finalResponse = `Logged ${amountToLog} ml. You've had ${total} ml so far today, leaving ${remaining} ml to reach your ${goal} ml goal (${percent}% completed). Keep it up!`;
          }

          trace.push({
            step_number: 6,
            type: 'decision',
            description: decisionDesc
          });
        } else {
          // Progress inquiry only
          trace.push({
            step_number: 2,
            type: 'tool_call',
            tool: 'get_progress',
            arguments: {}
          });

          const progressRes = executeGetProgress(currentMem);
          trace.push({
            step_number: 3,
            type: 'tool_result',
            tool: 'get_progress',
            result: progressRes
          });

          trace.push({
            step_number: 4,
            type: 'decision',
            description: `Retrieved current status (${progressRes.today_intake_ml}/${progressRes.daily_goal_ml} ml). Formulating summary response.`
          });

          if (userLower.includes('how much more') || userLower.includes('remaining') || userLower.includes('need')) {
            if (progressRes.goal_met) {
              finalResponse = `You have already met your daily target! You've logged ${progressRes.today_intake_ml} ml today (daily goal is ${progressRes.daily_goal_ml} ml).`;
            } else {
              finalResponse = `You need ${progressRes.remaining_ml} ml more to reach your ${progressRes.daily_goal_ml} ml goal today. You have had ${progressRes.today_intake_ml} ml so far (${progressRes.progress_percent}%).`;
            }
          } else {
            finalResponse = `You have had ${progressRes.today_intake_ml} ml of water today. Your daily goal is ${progressRes.daily_goal_ml} ml, leaving ${progressRes.remaining_ml} ml remaining (${progressRes.progress_percent}% completed).`;
          }
        }
      }

      // Ask Gemini to refine the grounded response through the server-side API.
      try {
        const geminiResponse = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userText,
            state: executeGetProgress(currentMem),
            local_response: finalResponse
          })
        });

        if (geminiResponse.ok) {
          const data = await geminiResponse.json();
          if (typeof data.response === 'string' && data.response.trim()) {
            finalResponse = data.response;
            trace.push({
              step_number: trace.length + 1,
              type: 'observation',
              description: 'Gemini refined the verified hydration response through the secure server API.'
            });
          }
        }
      } catch {
        // The deterministic response remains available when Gemini is unavailable.
      }

      // Record Turn in ConversationMemory
      const turnRecord: TurnRecord = {
        turn_index: currentMem.history.length + 1,
        timestamp: new Date().toISOString(),
        user_message: userText,
        plan: planDesc,
        steps: trace,
        final_response: finalResponse,
        intake_at_turn: currentMem.today_intake_ml,
        goal_at_turn: currentMem.daily_goal_ml
      };

      currentMem.history = [...currentMem.history, turnRecord];

      setMemory(currentMem);
      setLatestTrace(trace);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: finalResponse,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
      setIsProcessing(false);
    }, 400);
  };

  const handleResetMemory = () => {
    setMemory({
      daily_goal_ml: 2500,
      today_intake_ml: 0,
      logs: [],
      history: []
    });
    setLatestTrace([]);
    setMessages([
      {
        role: 'assistant',
        content: "Memory has been reset. Daily goal is 2500 ml and current intake is 0 ml. How much water did you drink?",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  const circumference = 2 * Math.PI * 58;
  const strokeDashoffset = circumference - (Math.min(100, progress_percent) / 100) * circumference;

  return (
    <div className="flex flex-col min-h-screen w-full text-slate-900 p-4 md:p-6 overflow-hidden">
      {/* Header */}
      <header className="flex flex-col gap-4 md:flex-row md:justify-between md:items-center mb-5 bg-white/90 p-4 md:p-5 rounded-2xl shadow-sm border border-slate-200/80 backdrop-blur-sm">
        <div>
          <h1 className="text-2xl font-bold text-cyan-800 flex items-center gap-2 tracking-tight">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-50 text-lg">💧</span>
            Water Intake Coach
          </h1>
          <p className="mt-1 text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
            University Agentic AI Project • T16 Health (Plan-Act Agent • Real Tools • Memory)
          </p>
        </div>
        <div className="flex flex-col-reverse items-start gap-3 sm:flex-row sm:items-center md:justify-end">
          <button
            onClick={handleResetMemory}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
            title="Reset conversation memory"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Session
          </button>
          <div className="text-right hidden sm:block">
            <p className="text-[10px] leading-tight text-slate-400 max-w-[320px] italic">
              Disclaimer: This project provides simple hydration tracking for demonstration purposes. It does not provide medical advice. Individual hydration needs vary.
            </p>
          </div>
        </div>
      </header>

      {/* Main 3-Column Agentic Layout matching Clean Minimalism */}
      <main className="flex flex-col lg:flex-row gap-5 flex-1 min-h-0">
        {/* Left Column: Progress Gauge & Memory State */}
        <section className="w-full lg:w-1/4 flex flex-col gap-4 overflow-y-auto">
          {/* Daily Progress Card */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-blue-500" />
                Daily Progress
              </h2>
              <button
                onClick={() => setShowGoalModal(!showGoalModal)}
                className="text-[11px] text-blue-600 font-semibold hover:underline"
              >
                Edit Goal
              </button>
            </div>

            {/* Circular Gauge */}
            <div className="flex flex-col items-center justify-center py-2">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="64"
                    cy="64"
                    r="58"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="transparent"
                    className="text-slate-100"
                  />
                  <circle
                    cx="64"
                    cy="64"
                    r="58"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="transparent"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    className="text-blue-500 transition-all duration-500 ease-out"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-slate-800">{progress_percent}%</span>
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">
                    {goal_met ? 'Goal Met' : 'Reached'}
                  </span>
                </div>
              </div>
            </div>

            {showGoalModal && (
              <div className="mb-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                <label className="text-[11px] font-semibold text-slate-600 block mb-1">Update Goal (ml):</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={customGoalInput}
                    onChange={e => setCustomGoalInput(e.target.value)}
                    className="flex-1 px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                  />
                  <button
                    onClick={() => {
                      const g = parseInt(customGoalInput, 10);
                      if (g > 0) {
                        setMemory(prev => ({ ...prev, daily_goal_ml: g }));
                        setShowGoalModal(false);
                      }
                    }}
                    className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-semibold"
                  >
                    Save
                  </button>
                </div>
              </div>
            )}

            {/* Progress Metrics List */}
            <div className="space-y-2.5 mt-2">
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-1">
                  <Droplets className="w-3.5 h-3.5 text-blue-500" />
                  Current Intake
                </span>
                <span className="text-sm font-bold text-slate-800">{memory.today_intake_ml} ml</span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-slate-50 rounded-lg">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-1">
                  <Target className="w-3.5 h-3.5 text-slate-400" />
                  Daily Goal
                </span>
                <span className="text-sm font-bold text-slate-800">{memory.daily_goal_ml} ml</span>
              </div>
              <div className="flex justify-between items-center p-2.5 bg-blue-50 border border-blue-100 rounded-lg text-blue-700">
                <span className="text-xs font-medium">Remaining Target</span>
                <span className="text-sm font-bold">{remaining_ml} ml</span>
              </div>
            </div>
          </div>

          {/* Conversation Memory State Card */}
          <div className="bg-slate-900 p-5 rounded-2xl text-white shadow-sm flex flex-col">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-blue-400" />
                Memory State
              </h2>
              <span className="text-[10px] text-blue-400 bg-slate-800 px-2 py-0.5 rounded font-mono">
                {memory.history.length} turns
              </span>
            </div>
            <div className="space-y-2 font-mono text-[11px]">
              <div className="p-2 bg-slate-800 rounded border border-slate-700 flex justify-between">
                <span className="text-blue-400">"daily_goal_ml":</span>
                <span className="text-emerald-400 font-bold">{memory.daily_goal_ml}</span>
              </div>
              <div className="p-2 bg-slate-800 rounded border border-slate-700 flex justify-between">
                <span className="text-blue-400">"today_intake_ml":</span>
                <span className="text-emerald-400 font-bold">{memory.today_intake_ml}</span>
              </div>
              <div className="p-2 bg-slate-800 rounded border border-slate-700 flex justify-between">
                <span className="text-blue-400">"logs_count":</span>
                <span className="text-slate-300">{memory.logs.length}</span>
              </div>
              <div className="p-2 bg-slate-800 rounded border border-slate-700 flex justify-between">
                <span className="text-blue-400">"goal_status":</span>
                <span className={goal_exceeded ? 'text-purple-400' : goal_met ? 'text-emerald-400' : 'text-amber-400'}>
                  {goal_exceeded ? '"exceeded"' : goal_met ? '"reached"' : '"in_progress"'}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Center Column: Conversation & Quick Evaluation Scenarios */}
        <section className="flex-1 min-h-[30rem] flex flex-col bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          {/* Quick Scenario Buttons for Teacher / Evaluator */}
          <div className="p-3 border-b border-slate-100 bg-slate-50/80 flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1 mr-1">
              <Sparkles className="w-3 h-3 text-blue-500" />
              Demo Scenarios:
            </span>
            <button
              onClick={() => handleAgentRun("I just drank 500 ml of water.")}
              className="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-600 border border-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
            >
              1. Log 500 ml
            </button>
            <button
              onClick={() => handleAgentRun("I drank another 300 ml.")}
              className="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-600 border border-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
            >
              2. Add 300 ml
            </button>
            <button
              onClick={() => handleAgentRun("How much have I had today?")}
              className="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-600 border border-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
            >
              Check Progress
            </button>
            <button
              onClick={() => handleAgentRun("I drank 1700 ml from my sports jug.")}
              className="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-600 border border-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors"
            >
              3. Reach Goal
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-6 space-y-4 overflow-y-auto">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start items-start gap-3'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0 text-sm shadow-xs">
                    🤖
                  </div>
                )}
                <div
                  className={`p-3.5 rounded-2xl text-sm leading-relaxed max-w-[82%] shadow-xs ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-slate-100 text-slate-800 rounded-tl-none border border-slate-200'
                  }`}
                >
                  <p>{msg.content}</p>
                  <span
                    className={`block text-[10px] mt-1.5 font-medium ${
                      msg.role === 'user' ? 'text-blue-200 text-right' : 'text-slate-400 text-left'
                    }`}
                  >
                    {msg.time}
                  </span>
                </div>
              </div>
            ))}

            {isProcessing && (
              <div className="flex justify-start items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 flex-shrink-0 animate-pulse">
                  🤖
                </div>
                <div className="bg-slate-100 text-slate-500 p-3 rounded-2xl rounded-tl-none text-xs border border-slate-200 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                  Agent analyzing request, executing tool calls, and updating memory...
                </div>
              </div>
            )}
          </div>

          {/* Quick Water Quantity Chips + Input Bar */}
          <div className="p-4 border-t border-slate-100 bg-slate-50">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[11px] text-slate-500 font-semibold">Quick Log:</span>
              {[250, 500, 750, 1000].map(amt => (
                <button
                  key={amt}
                  onClick={() => handleAgentRun(`I drank ${amt} ml of water.`)}
                  className="px-2.5 py-0.5 text-xs bg-white border border-slate-200 rounded-full hover:border-blue-400 hover:text-blue-600 text-slate-600 transition-colors"
                >
                  +{amt} ml
                </button>
              ))}
            </div>

            <form
              onSubmit={e => {
                e.preventDefault();
                handleAgentRun(inputMessage);
              }}
              className="flex gap-2 bg-white border border-slate-200 rounded-xl p-2 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-xs"
            >
              <input
                type="text"
                value={inputMessage}
                onChange={e => setInputMessage(e.target.value)}
                placeholder="Tell the agent what you drank (e.g. 'I had 500 ml') or ask progress..."
                className="flex-1 bg-transparent px-3 text-sm outline-none text-slate-800 placeholder-slate-400"
              />
              <button
                type="submit"
                disabled={!inputMessage.trim() || isProcessing}
                className="bg-blue-600 disabled:opacity-50 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-1.5 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                Send
              </button>
            </form>
          </div>
        </section>

        {/* Right Column: Agentic Multi-Step Trace */}
        <section className="w-full lg:w-1/3 min-h-[20rem] flex flex-col bg-slate-100/90 rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-4 border-b border-slate-200 bg-slate-200/80 flex justify-between items-center">
            <h2 className="text-xs font-bold uppercase tracking-widest text-slate-700 flex items-center gap-1.5">
              <Cpu className="w-4 h-4 text-blue-600" />
              Agentic Multi-Step Trace
            </h2>
            <span className="px-2 py-0.5 rounded text-[10px] bg-green-200 text-green-800 font-bold tracking-wider">
              ACTIVE
            </span>
          </div>

          <div className="flex-1 p-4 font-mono text-[11px] space-y-3.5 overflow-y-auto">
            {latestTrace.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <Cpu className="w-8 h-8 mx-auto mb-2 opacity-40 text-slate-500" />
                <p className="font-sans text-xs">No active execution trace.</p>
                <p className="font-sans text-[11px] text-slate-400 mt-1">
                  Send a message or click a demo scenario to inspect the multi-step Plan-Act-Observe-Decide loop.
                </p>
              </div>
            ) : (
              latestTrace.map((step, idx) => {
                if (step.type === 'plan') {
                  return (
                    <div key={idx} className="border-l-3 border-blue-500 pl-3 py-1 bg-white/70 rounded-r-lg p-2 border border-slate-200">
                      <p className="text-blue-600 font-bold mb-0.5 flex items-center gap-1">
                        <span>[Step {step.step_number}]</span> Planning
                      </p>
                      <p className="text-slate-700 font-sans text-xs leading-tight">{step.description}</p>
                    </div>
                  );
                } else if (step.type === 'tool_call') {
                  return (
                    <div key={idx} className="border-l-3 border-orange-500 pl-3 py-1 bg-white/70 rounded-r-lg p-2 border border-slate-200">
                      <p className="text-orange-600 font-bold mb-1 flex items-center gap-1">
                        <span>[Step {step.step_number}]</span> Action: Tool Call
                      </p>
                      <div className="bg-slate-900 text-slate-100 p-2 rounded text-[10px] font-mono overflow-x-auto">
                        <span className="text-purple-400 font-bold">{step.tool}</span>(
                        {step.arguments && Object.keys(step.arguments).length > 0 ? (
                          <span className="text-amber-300">{JSON.stringify(step.arguments)}</span>
                        ) : ''}
                        )
                      </div>
                    </div>
                  );
                } else if (step.type === 'tool_result') {
                  return (
                    <div key={idx} className="border-l-3 border-purple-500 pl-3 py-1 bg-white/70 rounded-r-lg p-2 border border-slate-200">
                      <p className="text-purple-600 font-bold mb-1 flex items-center gap-1">
                        <span>[Step {step.step_number}]</span> Observation: Tool Result
                      </p>
                      <pre className="bg-slate-50 border border-slate-200 p-2 rounded text-[10px] font-mono text-slate-800 overflow-x-auto max-h-36">
                        {JSON.stringify(step.result, null, 2)}
                      </pre>
                    </div>
                  );
                } else if (step.type === 'decision') {
                  return (
                    <div key={idx} className="border-l-3 border-green-500 pl-3 py-1 bg-white/70 rounded-r-lg p-2 border border-slate-200">
                      <p className="text-green-600 font-bold mb-0.5 flex items-center gap-1">
                        <span>[Step {step.step_number}]</span> Final Decision & Evaluation
                      </p>
                      <p className="text-slate-700 font-sans text-xs italic leading-tight">{step.description}</p>
                    </div>
                  );
                }
                return null;
              })
            )}
          </div>

          <div className="p-3 bg-slate-200/90 text-center border-t border-slate-300">
            <span className="text-[10px] text-slate-600 uppercase font-bold tracking-wider">
              {latestTrace.length > 0
                ? `Loop Completed in ${latestTrace.length} Steps`
                : 'Plan → Act → Observe → Decide Loop'}
            </span>
          </div>
        </section>
      </main>
    </div>
  );
}
