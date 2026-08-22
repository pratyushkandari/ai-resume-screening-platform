
import React from "react";


export default function FileInput({ onChange, accept = ".doc,.docx,.pdf" }) {

  return (

    <label
      style={{
        display: "block",            // makes the label a block element (takes full width)
        padding: "10px",             // inner spacing
        border: "2px dashed #bbb",   // gray dashed border to indicate "drop zone"
        borderRadius: "8px",         // smooth rounded corners
        textAlign: "center",         // centers the text horizontally
        cursor: "pointer",           // shows pointer cursor when hovered
        background: "#fafafa",       // light gray background
        transition: "0.3s ease all", // smooth hover animation (for future effects)
      }}
    >
      {/* -----------------------------------------------------------
          📥 Hidden File Input
          -----------------------------------------------------------
          - The <input> element is the actual file selector.
          - It is hidden using style={{ display: "none" }}.
          - When the user clicks on the label, this input is triggered automatically.
          - The `onChange` prop handles the event when a file is chosen.
      */}
      <input
        type="file"          // Tells the browser this input selects files
        accept={accept}      // Restricts file types (passed from props)
        onChange={onChange}  // Calls the parent-provided handler when file is chosen
        style={{ display: "none" }} // hides default input styling completely
      />

      {/* -----------------------------------------------------------
          🧾 Visible Text / Icon Section
          -----------------------------------------------------------
          - This is what the user actually sees inside the upload box.
          - You can change the emoji or text for better UX.
      */}
      <span style={{ color: "#333" }}>📄 Click to choose a file</span>
    </label>
  );
}
