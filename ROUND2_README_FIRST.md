# Start here — repaired source

Extract the complete ZIP, then follow the external-venv commands at the top of WINDOWS_SETUP.md. Do not delete either existing venv or personal data.

125 automated tests passed on Linux. Physical Windows voice/account acceptance is pending; see docs/WINDOWS_ACCEPTANCE_ROUND2.md.

Live config retains the existing Gemini model and google-genai==2.29.0. Only a single plausible API key is accepted. Start Listening, Ctrl+Space and local voice diagnostics remain independent of provider authentication. Hey Jarvis is the supported pretrained wake phrase. Full offline speech recognition is not implemented.

Read docs/ROUND2_REPAIR_REPORT.md for the root causes, tests, dependency policy, security changes and remaining risks.
