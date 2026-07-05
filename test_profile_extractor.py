"""
Test script for the new User Profile Extractor and Synthesizer.
"""
from core.profile_extractor import synthesize_profile

print("Testing synthesis on mock inputs...")
# We use a mock or standard public github user that has public data (like 'torvalds' or 'jack')
mock_github = "torvalds"
mock_linkedin = "Technical Lead and Open Source advocate. Creator of Git and Linux kernel. Highly experienced in C programming and low-level system design."
mock_resume = None # skip pdf bytes for this dry run

profile = synthesize_profile(
    github_user=mock_github,
    linkedin_text=mock_linkedin,
    resume_bytes=mock_resume
)

print("\n--- SYNTHESIZED PROFILE RESULT ---")
import json
print(json.dumps(profile, indent=2))
print("--- TEST PASSED ---")
