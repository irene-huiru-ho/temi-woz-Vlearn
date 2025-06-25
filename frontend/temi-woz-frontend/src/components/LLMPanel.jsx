import React from "react";

const LLMPanel = ({ response }) => {
  return (
    <div className="mt-4">
      <h4>🧠 LLM Analysis</h4>
      <div style={styles.container}>
        {response ? (
          <div style={styles.response}>{response}</div>
        ) : (
          <p>No response yet. Click 'Send to LLM' on an image.</p>
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    paddingRight: "1rem",
    maxHeight: "400px",
    overflowY: "auto",
    backgroundColor: "#fafafa",
    borderRadius: "8px",
    border: "1px solid #ddd",
    fontFamily: "monospace",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    response: {
      fontSize: "14px",
      color: "#333",
      lineHeight: "1.6",
    },
  },
};

export default LLMPanel;
