// =============================================================================================
//  FILE: frontend/src/hooks/useUpload.js (or frontend/src/components/useUpload.js)
// =============================================================================================
//
//  PURPOSE OF THIS FILE:
// ---------------------------------------------------------------------------------------------
// This is a **React Custom Hook** named `useUpload`.
//
// Custom hooks are reusable logic functions in React — they let you reuse stateful logic
// (like upload progress tracking or API calls) without rewriting the same code multiple times.
//
//  In this project:
// - `useUpload` handles uploading files (like resumes) to the FastAPI backend.
// - It automatically tracks upload progress (%), handles errors, and stores parsed results.
// - You can use it inside any React component — for example in UploadResume.jsx.
//
// Example usage in another file:
//   const { uploadFile, progress, parsed, reset } = useUpload("/api/resumes/upload");
//   uploadFile(selectedFile);
//
// ---------------------------------------------------------------------------------------------
//  WINDOWS PATH (for reference):
//   C:\pbldbms\frontend\src\hooks\useUpload.js
//
// ▶ Run Frontend (Windows PowerShell):
//   cd C:\pbldbms\frontend
//   npm run dev
//   → open http://localhost:5173
//
// ▶ Backend (FastAPI) must be running:
//   cd C:\pbldbms\backend
//   .\venv\Scripts\Activate.ps1
//   uvicorn app.main:app --reload
//
// =============================================================================================


// ---------------------------------------------------------------------------------------------
//  STEP 1️: IMPORT REQUIRED LIBRARIES
// ---------------------------------------------------------------------------------------------
import { useState } from "react";   // React Hook: lets us store & update upload progress and parsed data
import api from "../api";          // Axios instance: pre-configured to connect with FastAPI backend
import { toast } from "react-toastify"; // Toast notifications for success/error messages


// =============================================================================================
//  STEP 2️: DEFINE THE CUSTOM HOOK — useUpload()
// =============================================================================================
//
// This hook manages upload logic and progress tracking for any file.
// You can call it with a custom API endpoint, or it defaults to "/api/resumes/upload".
// ---------------------------------------------------------------------------------------------
export default function useUpload(endpoint = "/api/resumes/upload") {

  // -------------------------------------------------------------------------------------------
  //  STEP 3️: STATE VARIABLES
  // -------------------------------------------------------------------------------------------
  //
  // These variables hold information about the current upload:
  //   progress → number between 0–100 showing upload progress %
  //   parsed   → stores any parsed JSON/text returned from backend after upload
  // -------------------------------------------------------------------------------------------
  const [progress, setProgress] = useState(0);
  const [parsed, setParsed] = useState(null);


  // ===========================================================================================
  // ⬆ STEP 4️: FUNCTION — uploadFile(file)
  // ===========================================================================================
  //
  // Handles the entire upload process for one file.
  //   ✅ Validates file selection
  //   ✅ Sends POST request to backend
  //   ✅ Updates progress bar while uploading
  //   ✅ Stores backend response in “parsed” variable
  //
  // Works perfectly with FastAPI’s “/api/resumes/upload” route.
  // -------------------------------------------------------------------------------------------
  const uploadFile = async (file) => {

    //  Step 1: Basic validation
    if (!file) {
      toast.error("⚠️ Please select a file first");
      return null; // stop execution if no file
    }

    //  Step 2: Create FormData (required for sending files in HTTP)
    // FormData automatically formats data as “multipart/form-data”
    // which FastAPI can read using `UploadFile`.
    const formData = new FormData();
    formData.append("file", file);  // attach file object with key name “file”

    try {
      //  Step 3: Send HTTP POST request using axios (through api.js)
      const res = await api.post(endpoint, formData, {
        headers: { "Content-Type": "multipart/form-data" },

        // onUploadProgress is called multiple times during upload,
        // allowing us to display a progress bar in real time.
        onUploadProgress: (ev) => {
          // ev.loaded → bytes uploaded so far
          // ev.total  → total file size in bytes
          const pct = Math.round((ev.loaded / ev.total) * 100);
          setProgress(pct); // updates state so React can display percentage
        },
      });

      //  Step 4: Parse backend response
      //
      // Backend may return extracted info from resume (like name, email, skills, etc.)
      // under keys like “parsed” or “parsed_json”.
      const parsedData = res.data?.parsed ?? res.data?.parsed_json ?? null;
      setParsed(parsedData); // save parsed info in state

      toast.success("✅ File uploaded successfully!");
      return res.data; // return full backend response for further use

    } catch (err) {
      //  Step 5: Error handling
      console.error(err);
      toast.error("❌ Upload failed — check backend logs or internet connection");
      return null;
    }
  };


  // ===========================================================================================
  //  STEP 5️: FUNCTION — reset()
  // ===========================================================================================
  //
  // Resets the hook’s internal state (useful if you want to start a new upload).
  // -------------------------------------------------------------------------------------------
  const reset = () => {
    setProgress(0);   // reset progress bar
    setParsed(null);  // clear parsed data
  };


  // ===========================================================================================
  // STEP 6️: RETURN VALUES
  // ===========================================================================================
  //
  // Custom hooks in React return an object containing functions and data
  // that can be used inside other components.
  //
  // Here we return:
  //   - uploadFile: function to upload the file
  //   - progress:   numeric progress percentage
  //   - parsed:     parsed response (if backend sends structured data)
  //   - reset:      function to clear upload state
  // -------------------------------------------------------------------------------------------
  return { uploadFile, progress, parsed, reset };
}


// =============================================================================================
//  HOW TO USE THIS HOOK IN YOUR PROJECT
// =============================================================================================
//
// Example: inside UploadResume.jsx
//
// import useUpload from "../hooks/useUpload";
//
// export default function UploadResume() {
//   const { uploadFile, progress, parsed, reset } = useUpload("/api/resumes/upload");
//
//   async function handleUploadClick() {
//     const fileInput = document.querySelector("#resume-input");
//     const file = fileInput.files[0];
//     await uploadFile(file);
//   }
//
//   return (
//     <div>
//       <input id="resume-input" type="file" />
//       <button onClick={handleUploadClick}>Upload</button>
//       <div>Progress: {progress}%</div>
//     </div>
//   );
// }
//
// ---------------------------------------------------------------------------------------------
// Backend endpoint used: /api/resumes/upload (FastAPI)
// - Accepts file via FormData
// - Extracts text and metadata from resume
// - Returns structured info (parsed fields)
//
// =============================================================================================


// =============================================================================================
//  WINDOWS-SPECIFIC NOTES AND DEBUGGING
// =============================================================================================
//
// ▶ Frontend Commands (PowerShell):
//   cd C:\pbldbms\frontend
//   npm run dev
//   → Open http://localhost:5173
//
// ▶ Backend Commands:
//   cd C:\pbldbms\backend
//   .\venv\Scripts\Activate.ps1
//   uvicorn app.main:app --reload
//
// ▶ Common Windows issues:
//
//   ❌ Error: “Upload failed — check backend logs”
//      → Backend might not be running or endpoint path is wrong.
//        Verify: http://127.0.0.1:8000/docs
//
//   ❌ Error: “Network Error”
//      → Backend server is not reachable (check PowerShell FastAPI logs).
//
//   ❌ Progress not updating
//      → Some browsers (like older Edge versions) may limit progress tracking.
//        Use Chrome for best experience.
//
// ▶ Tip for VS Code on Windows:
//   - Use "Ctrl + `" to open integrated PowerShell.
//   - Save (Ctrl + S) triggers Vite auto-refresh instantly.
//
// =============================================================================================
//
// ✅ TL;DR (BEGINNER SUMMARY):
// ---------------------------------------------------------------------------------------------
// 🟢 `useUpload()` is a reusable hook that uploads files to the backend.
// 🟢 Tracks progress and parses backend responses.
// 🟢 Handles success/error notifications with Toastify.
// 🟢 Works seamlessly on Windows with PowerShell & FastAPI backend.
// 🟢 Great for uploading resumes, datasets, or documents in other components too.
// =============================================================================================
