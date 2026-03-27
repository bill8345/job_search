"""Resume parser - extracts skills and keywords from resume.md."""

from __future__ import annotations

import re
from pathlib import Path


def parse_resume(resume_path: str = "resume.md") -> dict:
    """Parse a markdown resume into structured data.
    
    Returns a dict with:
        - skills: list of skill keywords
        - experience: list of experience descriptions
        - education: list of education entries
        - desired_titles: list of desired job titles
        - raw_text: full resume text
    """
    path = Path(resume_path)
    if not path.exists():
        print(f"⚠️  找不到履歷檔案: {resume_path}")
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "desired_titles": [],
            "raw_text": "",
        }

    text = path.read_text(encoding="utf-8")
    
    result = {
        "skills": _extract_skills(text),
        "experience": _extract_section(text, ["工作經驗", "經歷", "Experience"]),
        "education": _extract_section(text, ["學歷", "Education"]),
        "desired_titles": _extract_section(text, ["期望職位", "Desired"]),
        "raw_text": text,
    }
    
    return result


def _extract_skills(text: str) -> list[str]:
    """Extract skills from the Skills section and inline mentions."""
    skills = []
    
    # Find skills section
    skill_section = _extract_section(text, ["技能", "Skills", "專長"])
    
    for line in skill_section:
        # Split by common delimiters
        parts = re.split(r"[,，、/|]", line)
        for part in parts:
            clean = part.strip().strip("-").strip("*").strip()
            if clean and len(clean) < 50:  # Reasonable skill length
                skills.append(clean)
    
    return skills


def _extract_section(text: str, section_names: list[str]) -> list[str]:
    """Extract content from a named section of the resume."""
    lines = text.split("\n")
    content = []
    in_section = False
    
    for line in lines:
        stripped = line.strip()
        
        # Check if this is a section header
        if stripped.startswith("#"):
            header = stripped.lstrip("#").strip()
            if any(name.lower() in header.lower() for name in section_names):
                in_section = True
                continue
            elif in_section:
                # We've hit the next section
                break
        
        if in_section and stripped:
            # Clean up list markers
            clean = stripped.lstrip("-").lstrip("*").lstrip("0123456789.").strip()
            if clean:
                content.append(clean)
    
    return content
