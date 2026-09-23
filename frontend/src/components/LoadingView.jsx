import React, { useState, useEffect } from 'react';
import { Sparkles, Brain, Database, CheckCircle2 } from 'lucide-react';

const STEPS = [
  { text: 'Ingesting document content...', icon: Sparkles },
  { text: 'Calling Snowflake Cortex AI (openai-gpt-5)...', icon: Brain },
  { text: 'Extracting structured actions & deadlines...', icon: CheckCircle2 },
  { text: 'Saving intelligence to DECISIONFLOW_DB.PUBLIC.DOCUMENTS...', icon: Database },
];

export default function LoadingView({ isPdf = false }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentStep((prev) => (prev < STEPS.length - 1 ? prev + 1 : prev));
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="card loading-box">
      <div className="loading-spinner-ring"></div>
      <h3 className="loading-heading">
        Analyzing {isPdf ? 'PDF Document' : 'Text'} with Cortex AI
      </h3>
      <p className="loading-subtext">
        Transforming complex unstructured directives into clean, prioritized decisions and actionable checklists.
      </p>

      <div className="loading-steps-pills">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isActive = idx === currentStep;
          const isDone = idx < currentStep;

          return (
            <div
              key={idx}
              className="loading-step-item"
              style={{
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--primary-700)' : isDone ? 'var(--text-main)' : 'var(--text-disabled)',
              }}
            >
              <div
                className={`step-indicator ${isActive ? 'active' : ''}`}
                style={{
                  backgroundColor: isDone ? '#22c55e' : isActive ? 'var(--primary-600)' : 'var(--border-focus)',
                  opacity: isActive || isDone ? 1 : 0.4,
                }}
              />
              <Icon size={15} />
              <span>{step.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
