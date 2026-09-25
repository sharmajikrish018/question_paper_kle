"""
scripts/create_sample_files.py
Creates sample data files for demonstration.
Run directly: python scripts/create_sample_files.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def create_sample_question_bank():
    """Create sample_question_bank.xlsx with correct schema."""
    import openpyxl
    from config.settings import get_settings

    settings = get_settings()
    out_path = settings.sample_files_dir / "sample_question_bank.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Question Bank"

    # Header row
    headers = [
        "question_id", "course_name", "unit_number", "chapter_number",
        "chapter_name", "question_text", "bloom_level", "marks",
        "question_type", "difficulty", "model_answer"
    ]
    ws.append(headers)

    # Bold headers
    from openpyxl.styles import Font, PatternFill, Alignment
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Sample questions — NOTE: These are labelled as SAMPLE DATA only
    # Unit 1: Chapters 1-3, Unit 2: Chapters 4-6, Unit 3: Chapter 7
    sample_data = []

    unit_chapter_map = {
        1: [(1, "Introduction to Generative AI"), (2, "Probability and Generative Models"), (3, "Autoencoders")],
        2: [(4, "Generative Adversarial Networks"), (5, "Variational Autoencoders"), (6, "Normalizing Flows")],
        3: [(7, "Large Language Models and Applications")],
    }

    bloom_verbs = {
        "L2": [
            "Explain the concept of",
            "Describe the working of",
            "Summarize the key principles of",
            "Identify the main components of",
            "Illustrate how",
            "Define and elaborate on",
        ],
        "L3": [
            "Apply the concept of",
            "Analyze how",
            "Compare and contrast",
            "Design a solution using",
            "Evaluate the effectiveness of",
            "Construct an example demonstrating",
        ],
    }

    q_count = 0
    for unit_num, chapters in unit_chapter_map.items():
        for ch_num, ch_name in chapters:
            for bloom in ["L2", "L3"]:
                for i in range(10):
                    q_count += 1
                    verbs = bloom_verbs[bloom]
                    verb = verbs[i % len(verbs)]
                    q_id = f"GENAI-U{unit_num}-C{ch_num}-{bloom}-Q{i+1:02d}"
                    text = (
                        f"[SAMPLE] {verb} {ch_name} and its role in the "
                        f"Generative AI landscape. Discuss with suitable examples "
                        f"and diagrams. (Question {i+1} of {bloom} for {ch_name})"
                    )
                    answer = (
                        f"[SAMPLE MODEL ANSWER] This is a placeholder model answer "
                        f"for question {q_id}. The real question bank must contain "
                        f"faculty-approved answers."
                    )
                    difficulty = "medium" if i < 5 else "hard" if i < 8 else "easy"
                    sample_data.append([
                        q_id, "Generative AI", unit_num, ch_num, ch_name,
                        text, bloom, 10, "descriptive", difficulty, answer
                    ])

    for row in sample_data:
        ws.append(row)

    # Column widths
    col_widths = [20, 15, 6, 8, 30, 60, 8, 6, 12, 10, 50]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    # Add disclaimer
    disclaimer_row = len(sample_data) + 3
    ws.cell(row=disclaimer_row, column=1, value=(
        "⚠️ SAMPLE DATA ONLY — Not approved question bank. "
        "Replace with faculty-approved questions before use."
    ))
    ws.cell(row=disclaimer_row, column=1).font = Font(bold=True, color="FF0000")

    wb.save(str(out_path))
    print(f"Created: {out_path} ({len(sample_data)} sample questions)")
    return out_path


def create_sample_lesson_plan():
    """Create sample_lesson_plan.docx."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from config.settings import get_settings

    settings = get_settings()
    out_path = settings.sample_files_dir / "sample_lesson_plan.docx"

    doc = Document()
    doc.add_heading("Generative AI — Lesson Plan", level=0)
    doc.add_paragraph(
        "⚠️ SAMPLE LESSON PLAN ONLY — Replace with the actual approved lesson plan."
    ).runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)

    content = """
UNIT 1: FUNDAMENTALS OF GENERATIVE AI (3 Chapters)

Chapter 1: Introduction to Generative AI
Topics:
- Definition and scope of Generative AI
- History and evolution of generative models
- Applications: image synthesis, text generation, audio
- Discriminative vs. Generative models
- Overview of GAN, VAE, Flow-based and Diffusion models

Chapter 2: Probability and Generative Models
Topics:
- Probability distributions and density estimation
- Maximum Likelihood Estimation (MLE)
- Latent variable models
- Bayesian inference basics
- Explicit vs. implicit density models

Chapter 3: Autoencoders and Representation Learning
Topics:
- Basic autoencoder architecture
- Denoising autoencoders
- Sparse autoencoders
- Representation learning and latent space
- Applications of autoencoders

UNIT 2: ADVANCED GENERATIVE ARCHITECTURES (3 Chapters)

Chapter 4: Generative Adversarial Networks (GANs)
Topics:
- GAN framework: generator and discriminator
- Minimax game formulation
- Training dynamics and challenges
- Variants: DCGAN, WGAN, CycleGAN, StyleGAN
- Evaluation metrics: FID, IS

Chapter 5: Variational Autoencoders (VAEs)
Topics:
- VAE architecture and objective function
- Evidence Lower Bound (ELBO)
- Reparameterization trick
- Conditional VAEs
- Beta-VAE and disentangled representations

Chapter 6: Normalizing Flows and Diffusion Models
Topics:
- Invertible transformations
- Normalizing flows: NICE, RealNVP, Glow
- Score-based generative models
- Denoising Diffusion Probabilistic Models (DDPM)
- Stable Diffusion overview

UNIT 3: LARGE LANGUAGE MODELS (1 Chapter)

Chapter 7: Large Language Models and Applications
Topics:
- Transformer architecture recap
- Pre-training objectives: CLM, MLM
- GPT family, BERT, T5 overview
- Prompt engineering and in-context learning
- Fine-tuning: full, LoRA, PEFT
- Responsible AI and ethical considerations
- Hallucination, alignment, and safety
"""

    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            doc.add_paragraph("")
        elif line.startswith("UNIT"):
            doc.add_heading(line, level=1)
        elif line.startswith("Chapter"):
            doc.add_heading(line, level=2)
        elif line.startswith("Topics:"):
            doc.add_paragraph("Topics:", style="Heading 3")
        elif line.startswith("-"):
            doc.add_paragraph(line[2:], style="List Bullet")
        else:
            doc.add_paragraph(line)

    doc.save(str(out_path))
    print(f"Created: {out_path}")
    return out_path


def create_sample_university_template():
    """Create sample_university_template.docx with placeholders."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from config.settings import get_settings

    settings = get_settings()
    out_path = settings.sample_files_dir / "sample_university_template.docx"

    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Disclaimer
    disclaimer = doc.add_paragraph(
        "⚠️ SAMPLE TEMPLATE ONLY — Replace with official university template"
    )
    disclaimer.runs[0].font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
    disclaimer.runs[0].font.bold = True
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph("")

    # University header
    univ = doc.add_paragraph("{{UNIVERSITY_NAME}}")
    univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    univ.runs[0].font.size = Pt(16)
    univ.runs[0].font.bold = True

    dept = doc.add_paragraph("{{DEPARTMENT}}")
    dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    dept.runs[0].font.size = Pt(13)

    doc.add_paragraph("")

    # Exam details table
    table = doc.add_table(rows=2, cols=4)
    table.style = "Table Grid"
    cells = [
        ("Course:", "{{COURSE_NAME}} ({{COURSE_CODE}})"),
        ("Exam Type:", "{{EXAM_TYPE}}"),
        ("Duration:", "{{DURATION}}"),
        ("Max Marks:", "{{MAX_MARKS}}"),
        ("Academic Year:", "{{ACADEMIC_YEAR}}"),
        ("Set:", "{{SET_NAME}}"),
        ("Date:", "________________"),
        ("USN:", "________________"),
    ]
    for i, (label, value) in enumerate(cells[:8]):
        row_idx = i // 4
        col_idx = (i % 4)
        if row_idx < 2 and col_idx < 4:
            if col_idx < len(table.rows[row_idx].cells):
                cell = table.rows[row_idx].cells[col_idx]
                cell.text = f"{label} {value}"

    doc.add_paragraph("")

    # Instructions
    instr = doc.add_paragraph("General Instructions:")
    instr.runs[0].font.bold = True
    doc.add_paragraph("{{GENERAL_INSTRUCTIONS}}")

    doc.add_paragraph("")
    doc.add_paragraph("—" * 60)
    doc.add_paragraph("")

    # Question body placeholder
    qbody = doc.add_paragraph(
        "{{QUESTION_BODY}}"
    )
    qbody.runs[0].font.size = Pt(11)

    doc.save(str(out_path))
    print(f"Created: {out_path}")
    return out_path


def copy_template_to_active():
    """Copy sample template to university_templates for immediate use."""
    from config.settings import get_settings
    import shutil

    settings = get_settings()
    src = settings.sample_files_dir / "sample_university_template.docx"
    dst = settings.university_templates_dir / "sample_university_template.docx"
    if src.exists():
        shutil.copy2(src, dst)
        print(f"Copied template to: {dst}")


if __name__ == "__main__":
    print("Creating sample files...")
    create_sample_question_bank()
    create_sample_lesson_plan()
    create_sample_university_template()
    copy_template_to_active()
    print("\nAll sample files created successfully!")
    print("\nIMPORTANT: These are SAMPLE files only.")
    print("Replace with real faculty-approved content before production use.")
