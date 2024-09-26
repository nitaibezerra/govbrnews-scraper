import json
import os
from collections import defaultdict
from datetime import datetime
from itertools import groupby

import markdown
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def process_augmented_news(directory_path):
    """
    Processes all JSON files in the specified directory, filters entries based on the 'is_ai_related_flag',
    adds an 'agency' attribute extracted from the filename, and returns a list of filtered dictionaries.

    Args:
        directory_path (str): The path to the directory containing the JSON files.

    Returns:
        list: A list of dictionaries where 'is_ai_related_flag' is True, with an added 'agency' attribute.

    The function also prints:
        - The total number of filtered entries.
        - The number of entries per agency.
    """
    # Initialize a list to hold all filtered entries and a dictionary for agency count
    filtered_entries = []
    agency_count = defaultdict(int)

    # Loop through all files in the directory
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            # Extract agency from the filename
            agency = filename.split("_")[0]

            # Read the JSON file
            with open(
                os.path.join(directory_path, filename), "r", encoding="utf-8"
            ) as file:
                data = json.load(file)

                # Filter entries where is_ai_related_flag is True
                for entry in data:
                    if entry.get("is_ai_related_flag", False):
                        # Add the agency attribute
                        entry["agency"] = agency
                        filtered_entries.append(entry)
                        # Count the entry for the agency
                        agency_count[agency] += 1

    # Print the number of returned entries and the amount by agency
    total_entries = len(filtered_entries)
    print(f"Total filtered entries: {total_entries}")
    for agency, count in agency_count.items():
        print(f"Agency '{agency}': {count} entries")

    return filtered_entries


# Mapping of agency keys to full names
agency_full_names = {
    "agricultura": "MAPA - Ministério da Agricultura e Pecuária",
    "agu": "AGU - Advocacia-Geral da União",
    "casacivil": "CC - Casa Civil",
    "cgu": "CGU - Controladoria-Geral da União",
    "cidades": "MCid - Ministério das Cidades",
    "cultura": "MinC - Ministério da Cultura",
    "defesa": "MD - Ministério da Defesa",
    "esporte": "ME - Ministério do Esporte",
    "fazenda": "MF - Ministério da Fazenda",
    "gestao": "MGI - Ministério da Gestão e Inovação em Serviços Públicos",
    "gsi": "GSI - Gabinete de Segurança Institucional",
    "igualdaderacial": "MIR - Ministério da Igualdade Racial",
    "mcom": "MCom - Ministério das Comunicações",
    "mcti": "MCTI - Ministério da Ciência, Tecnologia e Inovação",
    "mda": "MDA - Ministério do Desenvolvimento Agrário e Agricultura Familiar",
    "mdh": "MDHC - Ministério dos Direitos Humanos e Cidadania",
    "mdic": "MDIC - Ministério do Desenvolvimento, Indústria, Comércio e Serviços",
    "mdr": "MIDR - Ministério da Integração e Desenvolvimento Regional",
    "mds": "MDS - Ministério do Desenvolvimento e Assistência Social, Família e Combate à Fome",
    "mec": "MEC - Ministério da Educação",
    "memp": "MEMPP - Ministério do Empreendedorismo, da Microempresa e da Empresa de Pequeno Porte",
    "mj": "MJSP - Ministério da Justiça e Segurança Pública",
    "mma": "MMA - Ministério do Meio Ambiente e Mudança do Clima",
    "mme": "MME - Ministério de Minas e Energia",
    "mpa": "MPA - Ministério da Pesca e Aquicultura",
    "mre": "MRE - Ministério das Relações Exteriores",
    "mulheres": "MMulheres - Ministério das Mulheres",
    "planalto": "PR - Presidência da República",
    "planejamento": "MPO - Ministério do Planejamento e Orçamento",
    "portos": "MPAero - Ministério de Portos e Aeroportos",
    "previdencia": "MPS - Ministério da Previdência Social",
    "reconstrucaors": "SAR-RS - Secretaria para Apoio à Reconstrução do Rio Grande do Sul",
    "saude": "MS - Ministério da Saúde",
    "secom": "Secom - Secretaria de Comunicação Social",
    "secretariageral": "SGPR - Secretaria-Geral da Presidência da República",
    "sri": "SRI - Secretaria de Relações Institucionais",
    "trabalho-e-emprego": "MTE - Ministério do Trabalho e Emprego",
    "transportes": "MT - Ministério dos Transportes",
    "turismo": "MTur - Ministério do Turismo",
}


def generate_pdf_news_reportlab(newspaper_entries, pdf_filename):
    """
    Generates a PDF newspaper from the filtered news entries, sorted by the number of news items per agency in descending order using ReportLab.

    Args:
        newspaper_entries (list): A list of filtered news dictionaries from the process_augmented_news function.
        pdf_filename (str): The name of the output PDF file.

    The PDF will include:
        - A summary at the beginning with a list of agencies, their number of news articles, and links to their sections.
        - A section for each agency, with:
            - The full name of the agency.
            - For each news item:
                - The title of the news as a hyperlink.
                - The URL itself.
                - The date.
                - The AI mention.
    """

    # Group entries by agency and count the number of news items per agency
    agency_news_map = defaultdict(list)
    for entry in newspaper_entries:
        agency_news_map[entry["agency"]].append(entry)

    # Sort agencies by the number of news items in descending order
    sorted_agencies = sorted(
        agency_news_map.items(), key=lambda x: len(x[1]), reverse=True
    )

    # Create the document
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    story = []

    # Define styles
    styles = getSampleStyleSheet()
    summary_intro_style = ParagraphStyle(
        name="Summary",
        parent=styles["Normal"],
        fontSize=12,
        spaceAfter=6,
        leading=16,  # Line spacing
    )
    agency_style = ParagraphStyle(
        name="AgencyTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
        alignment=TA_LEFT,
    )
    news_title_style = ParagraphStyle(
        name="NewsTitle",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.blue,
        spaceAfter=6,
        leading=13,  # Line spacing
    )
    summary_style = ParagraphStyle(
        name="NewsTitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.blue,
        spaceAfter=8,
        leading=13,  # Line spacing
    )

    ai_mention_label_style = ParagraphStyle(
        name="ai_mention_label",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6,
    )
    ai_mention_style = ParagraphStyle(
        name="ai_mention",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=6,
    )

    # Add title
    story.append(Paragraph("AI news - gov.br", styles["Title"]))
    story.append(Spacer(1, 12))  # Add some space after the title

    # Calculate the max and min dates
    all_dates = [
        datetime.strptime(entry["date"], "%Y-%m-%d") for entry in newspaper_entries
    ]
    min_date = min(all_dates).strftime("%d/%m/%Y")
    max_date = max(all_dates).strftime("%d/%m/%Y")

    # Add introduction
    intro_text = (
        "As notícias a seguir foram extraídas de agências governamentais e "
        "possuem alguma <b>relação com o campo de Inteligência Artificial</b>. "
        f"O período coberto pelas notícias vai de <b>{min_date}</b> até "
        f"<b>{max_date}</b>. A identificação da relação com IA foi realizada por "
        "meio de um LLM (Large Language Model) e por isso pode conter erros. IA "
        "News é um projeto experimental desenvolvido no Gabinete do MGI."
    )
    story.append(Paragraph(intro_text, summary_intro_style))
    story.append(Spacer(1, 24))  # Add some space after the introduction

    # Add a summary section at the beginning
    story.append(Paragraph("<b>Notícias por órgão:</b>", styles["Heading1"]))
    story.append(Spacer(1, 12))

    for agency, entries in sorted_agencies:
        agency_full_name = agency_full_names.get(agency, agency.upper())
        link = f'- <a href="#{agency}">{agency_full_name} ({len(entries)} notícia{"s" if len(entries) > 1 else ""})</a>'
        story.append(Paragraph(link, summary_style))

    # Add a page break after the summary
    story.append(PageBreak())

    # Group entries by month within the agency
    for agency_index, (agency, entries) in enumerate(sorted_agencies):
        agency_full_name = agency_full_names.get(agency, agency.upper())

        # Sort the entries by date within the agency in ascending order
        entries.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))

        # Group the entries by year and month
        grouped_by_month = groupby(
            entries, key=lambda x: datetime.strptime(x["date"][:7], "%Y-%m")
        )

        # Add a page break before each new agency section, but skip the first one
        if agency_index > 0:
            story.append(PageBreak())

        # Add a new section for the agency with an anchor for internal linking
        story.append(Paragraph(f'<a name="{agency}"/>{agency_full_name}', agency_style))
        story.append(Spacer(1, 12))  # Add some space after the section title

        # Loop through each month group
        for year_month, month_entries in grouped_by_month:
            # Add a month header
            month_name = month_year_in_pt(year_month)
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<b>{month_name}</b>", summary_intro_style))

            # Add the news entry details for the month
            for entry in month_entries:
                # Title with hyperlink
                story.append(
                    Paragraph(
                        f'<a href="{entry["url"]}">{entry["title"]}</a>',
                        news_title_style,
                    )
                )

                # Prepare the table data for AI Mention, Tags, URL, and Date
                table_data = []

                # AI Mention
                if "ai_mention" in entry and entry["ai_mention"]:
                    table_data.append(
                        [
                            Paragraph("<b>Menção de IA:</b>", ai_mention_label_style),
                            Paragraph(
                                correct_html_tags(
                                    markdown.markdown(entry["ai_mention"])
                                ),
                                ai_mention_style,
                            ),
                        ]
                    )

                # Tags
                if entry.get("tags"):
                    tags_text = ", ".join(entry["tags"])
                    table_data.append(
                        [
                            Paragraph(
                                "Etiquetas:",
                                ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                            ),
                            Paragraph(
                                tags_text,
                                ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                            ),
                        ]
                    )

                # URL
                table_data.append(
                    [
                        Paragraph(
                            "URL:",
                            ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                        ),
                        Paragraph(
                            entry["url"],
                            ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                        ),
                    ]
                )

                # Format the date to dd/mm/yyyy
                formatted_date = datetime.strptime(entry["date"], "%Y-%m-%d").strftime(
                    "%d/%m/%Y"
                )
                table_data.append(
                    [
                        Paragraph(
                            "Data:",
                            ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                        ),
                        Paragraph(
                            formatted_date,
                            ParagraphStyle(name="GrayStyle", textColor=colors.gray),
                        ),
                    ]
                )

                # Create the table with two columns
                table = Table(table_data, colWidths=[1 * inch, 5 * inch])
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )

                # Add the table to the story
                story.append(table)
                story.append(Spacer(1, 12))  # Add some space before the next news entry

    # Build the PDF
    doc.build(story)


def correct_html_tags(html_text):
    """
    Corrects unclosed or improperly nested HTML tags in the provided string.

    Args:
        html_text (str): The HTML string to be corrected.

    Returns:
        str: A corrected HTML string.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    return str(soup)


def month_year_in_pt(data):
    # Map the months from English to Portuguese
    meses_portugues = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    # Extract month and year
    mes = data.month
    ano = data.year

    # Return formatted string
    return f"{meses_portugues[mes]}/{ano}"


filtered_news = process_augmented_news("./augmented_news")
generate_pdf_news_reportlab(filtered_news, "ai_news_newspaper.pdf")
