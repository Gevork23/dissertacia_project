# Bibliography Working List

> Working access date for web sources: 2026-05-12.

> Verification statuses distinguish source existence from final ГОСТ completeness. `needs verification` means the source appears real, but at least one bibliographic field should be checked against the publisher/library record before final submission.

## 1. Электронный документооборот и document management

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-DMS-001 | Reinsel, D.; Gantz, J.; Rydning, J. The Digitization of the World: From Edge to Core. IDC White Paper, sponsored by Seagate. | Industry white paper | 2018 | https://www.seagate.com/files/www-content/our-story/trends/files/idc-seagate-dataage-whitepaper.pdf | Рост объёма цифровых данных и документооборота как внешний контекст актуальности. | verified; official PDF; trust: medium/high |
| SRC-DMS-002 | International Organization for Standardization. ISO 15489-1:2016 Information and documentation — Records management — Part 1: Concepts and principles. | Standard | 2016 | https://www.iso.org/standard/62542.html | Document lifecycle, records management, метаданные, ответственность и контроль управления документами. | verified; official ISO page; trust: high |
| SRC-DMS-003 | Sprague, R. H. Electronic Document Management: Challenges and Opportunities for Information Systems Managers. MIS Quarterly. | Peer-reviewed article | 1995 | DOI: 10.2307/249710 | Классическое обоснование задач electronic document management и организационных ограничений. | verified; DOI/publisher metadata checked; trust: high |
| SRC-DMS-004 | Smith, H. A.; McKeen, J. D. Developments in Practice VIII: Enterprise Content Management. Communications of the Association for Information Systems. | Peer-reviewed article | 2003 | DOI: 10.17705/1CAIS.01204 | Границы ECM/DMS: хранение, управление контентом, процессы и enterprise context. | verified; DOI checked; trust: high |

## 2. Legal / нормативные документы как объект обработки

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-LEGAL-001 | Ashley, K. D. Artificial Intelligence and Legal Analytics: New Tools for Law Practice in the Digital Age. Cambridge University Press. | Book | 2017 | DOI: 10.1017/9781316761380 | Юридические документы как объект анализа; legal analytics; роль структуры и аргументации. | verified; publisher DOI/ISBN metadata checked; trust: high |
| SRC-LEGAL-002 | Palmirani, M.; Governatori, G.; Athan, T.; Boley, H.; Paschke, A.; Wyner, A. LegalRuleML Core Specification Version 1.0. OASIS Standard. | Official standard/specification | 2021 | https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html | Машиночитаемое представление юридических норм, provenance и tracking юридических утверждений. | verified; official OASIS standard; trust: high |
| SRC-LEGAL-003 | OASIS LegalDocML Technical Committee. Akoma Ntoso Version 1.0. OASIS Standard. | Official standard/specification | 2018 | https://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/akn-core-v1.0-os.html | Структурное представление законодательных, судебных и парламентских документов; metadata/document model. | verified; official OASIS standard; trust: high |

## 3. Text diff / document comparison

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-DIFF-001 | Wagner, R. A.; Fischer, M. J. The String-to-String Correction Problem. Journal of the ACM. | Peer-reviewed article | 1974 | DOI: 10.1145/321796.321811 | Классическая edit distance / string correction основа для сравнения последовательностей. | verified; ACM DOI checked; trust: high |
| SRC-DIFF-002 | Hunt, J. W.; Szymanski, T. G. A Fast Algorithm for Computing Longest Common Subsequences. Communications of the ACM. | Peer-reviewed article | 1977 | DOI: 10.1145/359581.359603 | LCS как базовый подход для diff/document comparison. | verified; ACM DOI checked; trust: high |
| SRC-DIFF-003 | Myers, E. W. An O(ND) Difference Algorithm and Its Variations. Algorithmica. | Peer-reviewed article | 1986 | DOI: 10.1007/BF01840446 | Классический efficient diff algorithm; baseline для текстового сравнения. | verified; DBLP/DOI checked; trust: high |
| SRC-DIFF-004 | Chawathe, S. S.; Rajaraman, A.; Garcia-Molina, H.; Widom, J. Change Detection in Hierarchically Structured Information. SIGMOD Record / SIGMOD Conference. | Peer-reviewed conference paper | 1996 | DOI: 10.1145/235968.233366 | Обоснование structured diff для иерархически структурированных документов. | verified; DOI/conference metadata checked; trust: high |
| SRC-DIFF-005 | Cobéna, G.; Abiteboul, S.; Marian, A. Detecting Changes in XML Documents. ICDE. | Peer-reviewed conference paper | 2002 | https://dblp.org/rec/conf/icde/CobenaAM02.html | XML/structured document comparison; изменения в структурированных документах. | needs verification; source existence checked, publisher DOI/pages require final library verification |
| SRC-DIFF-006 | Falleri, J.-R.; Morandat, F.; Blanc, X.; Martinez, M.; Monperrus, M. Fine-grained and Accurate Source Code Differencing. ASE. | Peer-reviewed conference paper | 2014 | DOI: 10.1145/2642937.2642982 | Tree/structure-aware differencing as analogy for structure-preserving comparison. | verified; DOI checked; trust: high |

## 4. NLP / document intelligence

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-DOCINT-001 | Xu, Y.; Li, M.; Cui, L.; Huang, S.; Wei, F.; Zhou, M. LayoutLM: Pre-training of Text and Layout for Document Image Understanding. KDD. | Peer-reviewed conference paper | 2020 | DOI: 10.1145/3394486.3403172 | Document intelligence: joint text/layout representation for document understanding. | verified; DOI/DBLP checked; trust: high |
| SRC-DOCINT-002 | Katti, A. R.; Reisswig, C.; Guder, C.; Brarda, S.; Bickel, S.; Höhne, J.; Faddoul, J.-B. Chargrid: Towards Understanding 2D Documents. EMNLP. | Peer-reviewed conference paper | 2018 | DOI: 10.18653/v1/D18-1476 | Layout-aware extraction and document understanding for semi-structured documents. | verified; ACL DOI checked; trust: high |
| SRC-DOCINT-003 | Lopresti, D. Optical Character Recognition Errors and Their Effects on Natural Language Processing. International Journal on Document Analysis and Recognition. | Peer-reviewed article | 2009 | DOI: 10.1007/s10032-009-0094-8 | Ошибки extraction/OCR как фактор качества downstream NLP pipeline. | verified; Springer DOI checked; trust: high |
| SRC-DOCINT-004 | Li, M.; Xu, Y.; Cui, L.; Huang, S.; Wei, F.; Li, Z.; Zhou, M. DocBank: A Benchmark Dataset for Document Layout Analysis. COLING. | Peer-reviewed conference paper / dataset paper | 2020 | https://www.microsoft.com/en-us/research/publication/docbank-a-benchmark-dataset-for-document-layout-analysis/ | Layout/document analysis datasets; token-level structure annotations. | verified; Microsoft Research publication page checked; trust: high |
| SRC-DOCINT-005 | Mathew, M.; Karatzas, D.; Jawahar, C. V. DocVQA: A Dataset for VQA on Document Images. WACV. | Peer-reviewed conference paper / dataset paper | 2021 | DOI: 10.1109/WACV48630.2021.00225 | Document understanding tasks where answers depend on document text and structure. | verified; university/publisher metadata checked; trust: high |

## 5. Legal NLP

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-LEGALNLP-001 | Zhong, H.; Xiao, C.; Tu, C.; Zhang, T.; Liu, Z.; Sun, M. How Does NLP Benefit Legal System: A Summary of Legal Artificial Intelligence. ACL. | Peer-reviewed conference paper / survey-style summary | 2020 | DOI: 10.18653/v1/2020.acl-main.466 | Обзор legal AI/NLP tasks, legal information extraction/classification and challenges. | verified; ACL Anthology DOI checked; trust: high |
| SRC-LEGALNLP-002 | Chalkidis, I.; Fergadiotis, M.; Malakasiotis, P.; Aletras, N.; Androutsopoulos, I. LEGAL-BERT: The Muppets straight out of Law School. Findings of EMNLP. | Peer-reviewed conference paper | 2020 | DOI: 10.18653/v1/2020.findings-emnlp.261 | Domain adaptation/pretraining for legal NLP. | verified; ACL Anthology DOI checked; trust: high |
| SRC-LEGALNLP-003 | Chalkidis, I.; Jana, A.; Hartung, D.; Bommarito, M.; Androutsopoulos, I.; Katz, D.; Aletras, N. LexGLUE: A Benchmark Dataset for Legal Language Understanding in English. ACL. | Peer-reviewed conference paper / benchmark | 2022 | DOI: 10.18653/v1/2022.acl-long.297 | Evaluation of legal language understanding models and legal NLP benchmarks. | verified; ACL Anthology DOI checked; trust: high |
| SRC-LEGALNLP-004 | Hendrycks, D.; Burns, C.; Chen, A.; Ball, S. CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review. NeurIPS Datasets and Benchmarks. | Peer-reviewed dataset paper | 2021 | https://proceedings.neurips.cc/paper/2021/hash/8c235f89a8143a28a1d6067e959dd858-Abstract.html | Expert annotation and legal document review dataset; illustrates annotation demands. | verified; NeurIPS/DBLP page checked; trust: high |
| SRC-LEGALNLP-005 | Lippi, M.; Pałka, P.; Contissa, G.; Lagioia, F.; Micklitz, H.-W.; Sartor, G.; Torroni, P. CLAUDETTE: An Automated Detector of Potentially Unfair Clauses in Online Terms of Service. Artificial Intelligence and Law. | Peer-reviewed article | 2019 | DOI: 10.1007/s10506-019-09243-2 | Legal text classification/extraction with expert validation context. | verified; DOI checked; trust: high |

## 6. LLM reliability and hallucinations

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-LLM-001 | Ji, Z.; Lee, N.; Frieske, R.; Yu, T.; Su, D.; Xu, Y.; Ishii, E.; Bang, Y. J.; Madotto, A.; Fung, P. Survey of Hallucination in Natural Language Generation. ACM Computing Surveys. | Peer-reviewed survey article | 2023 | DOI: 10.1145/3571730 | Definitions, causes and mitigation directions for hallucinations in NLG/LLM outputs. | verified; ACM DOI checked; trust: high |
| SRC-LLM-002 | Maynez, J.; Narayan, S.; Bohnet, B.; McDonald, R. On Faithfulness and Factuality in Abstractive Summarization. ACL. | Peer-reviewed conference paper | 2020 | DOI: 10.18653/v1/2020.acl-main.173 | Factuality/faithfulness issues in summarization; supports need for source-grounded verification. | verified; ACL DOI checked; trust: high |
| SRC-LLM-003 | Lewis, P.; Perez, E.; Piktus, A.; Petroni, F.; Karpukhin, V.; Goyal, N.; Küttler, H.; Lewis, M.; Yih, W.-t.; Rocktäschel, T.; Riedel, S.; Kiela, D. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS. | Peer-reviewed conference paper | 2020 | https://papers.nips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html | Grounded/retrieval-augmented generation and provenance-oriented alternatives to parametric-only generation. | verified; NeurIPS official page checked; trust: high |
| SRC-LLM-004 | Shuster, K.; Poff, S.; Chen, M.; Kiela, D.; Weston, J. Retrieval Augmentation Reduces Hallucination in Conversation. Findings of EMNLP. | Peer-reviewed conference paper | 2021 | DOI: 10.18653/v1/2021.findings-emnlp.320 | Evidence that retrieval grounding can reduce hallucination in generated responses. | verified; ACL DOI checked; trust: high |
| SRC-LLM-005 | Manakul, P.; Liusie, A.; Gales, M. J. F. SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models. EMNLP. | Peer-reviewed conference paper | 2023 | DOI: 10.18653/v1/2023.emnlp-main.557 | Hallucination detection/verification; supports cautious use of generated summaries. | verified; ACL DOI checked; trust: high |

## 7. Human-in-the-loop

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-HITL-001 | Amershi, S.; Cakmak, M.; Knox, W. B.; Kulesza, T. Power to the People: The Role of Humans in Interactive Machine Learning. AI Magazine. | Peer-reviewed article | 2014 | DOI: 10.1609/aimag.v35i4.2513 | Human role in interactive ML; expert feedback and oversight. | verified; DOI checked; trust: high |
| SRC-HITL-002 | Amershi, S.; Weld, D.; Vorvoreanu, M.; Fourney, A.; Nushi, B.; Collisson, P.; Suh, J.; Iqbal, S.; Bennett, P.; Inkpen, K.; Teevan, J.; Kikin-Gil, R.; Horvitz, E. Guidelines for Human-AI Interaction. CHI. | Peer-reviewed conference paper | 2019 | https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/ | Human-AI quality gates, interaction guidelines and human oversight. | verified; Microsoft Research/CHI page checked; trust: high |
| SRC-HITL-003 | Mosqueira-Rey, E.; Hernández-Pereira, E.; Alonso-Ríos, D.; Bobes-Bascarán, J.; Fernández-Leal, Á. Human-in-the-loop Machine Learning: A State of the Art. Artificial Intelligence Review. | Peer-reviewed review article | 2023 | DOI: 10.1007/s10462-022-10246-w | Обзор human-in-the-loop ML/NLP approaches and review patterns. | verified; Springer DOI checked; trust: high |
| SRC-HITL-004 | National Institute of Standards and Technology. Artificial Intelligence Risk Management Framework (AI RMF 1.0). NIST AI 100-1. | Official framework | 2023 | DOI: 10.6028/NIST.AI.100-1 | Risk management, oversight and responsible AI framing for decision-support systems. | verified; official NIST DOI checked; trust: high |

## 8. Automated question generation

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-AQG-001 | Kurdi, G.; Leo, J.; Parsia, B.; Sattler, U.; Al-Emari, S. A Systematic Review of Automatic Question Generation for Educational Purposes. International Journal of Artificial Intelligence in Education. | Peer-reviewed systematic review | 2020 | DOI: 10.1007/s40593-019-00186-y | Educational AQG methods, evaluation and limitations. | verified; Springer DOI checked; trust: high |
| SRC-AQG-002 | Heilman, M.; Smith, N. A. Good Question! Statistical Ranking for Question Generation. NAACL-HLT. | Peer-reviewed conference paper | 2010 | https://aclanthology.org/N10-1086/ | Question generation and ranking as draft selection problem. | verified; ACL Anthology page checked; trust: high |
| SRC-AQG-003 | Mulla, N.; Gharpure, P. Automatic Question Generation: A Review of Methodologies, Datasets, Evaluation Metrics, and Applications. Progress in Artificial Intelligence. | Peer-reviewed review article | 2023 | DOI: 10.1007/s13748-023-00295-9 | Recent overview of AQG methodologies, datasets, metrics and applications. | verified; Springer DOI checked; trust: high |
| SRC-AQG-004 | Gierl, M. J.; Lai, H. The Role of Item Models in Automatic Item Generation. International Journal of Testing. | Peer-reviewed article | 2012 | DOI: 10.1080/15305058.2011.635830 | Assessment item model design and automatic item generation. | verified; Taylor & Francis DOI checked; trust: high |
| SRC-AQG-005 | Haladyna, T. M.; Downing, S. M.; Rodriguez, M. C. A Review of Multiple-Choice Item-Writing Guidelines for Classroom Assessment. Applied Measurement in Education. | Peer-reviewed review article | 2002 | DOI: 10.1207/S15324818AME1503_5 | Quality constraints for multiple-choice questions and distractors. | verified; DOI/university metadata checked; trust: high |

## 9. Evaluation methodology

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-EVAL-001 | Manning, C. D.; Raghavan, P.; Schütze, H. Introduction to Information Retrieval. Cambridge University Press. | Book | 2008 | DOI: 10.1017/CBO9780511809071 | Precision, recall and information retrieval evaluation terminology. | verified; publisher DOI/ISBN metadata checked; trust: high |
| SRC-EVAL-002 | Sokolova, M.; Lapalme, G. A Systematic Analysis of Performance Measures for Classification Tasks. Information Processing & Management. | Peer-reviewed article | 2009 | DOI: 10.1016/j.ipm.2009.03.002 | Classification metrics: precision, recall, F-measure and multi-class evaluation. | verified; DOI checked; trust: high |
| SRC-EVAL-003 | Runeson, P.; Höst, M. Guidelines for Conducting and Reporting Case Study Research in Software Engineering. Empirical Software Engineering. | Peer-reviewed article | 2009 | DOI: 10.1007/s10664-008-9102-8 | Validity threats and empirical software engineering reporting. | verified; Springer DOI checked; trust: high |
| SRC-EVAL-004 | Wohlin, C.; Runeson, P.; Höst, M.; Ohlsson, M. C.; Regnell, B.; Wesslén, A. Experimentation in Software Engineering. Springer. | Book | 2012 | DOI: 10.1007/978-3-642-29044-2 | Experimental design, threats to validity, empirical interpretation. | verified; university/Springer DOI metadata checked; trust: high |

## 10. Software architecture and reproducibility

| ID | Source | Type | Year | URL/DOI | Used for | Verification |
|---|---|---|---:|---|---|---|
| SRC-ARCH-001 | Kleppmann, M.; Wiggins, A.; van Hardenberg, P.; McGranaghan, M. Local-first Software: You Own Your Data, in Spite of the Cloud. Onward! / SPLASH. | Peer-reviewed conference paper | 2019 | DOI: 10.1145/3359591.3359737 | Local-first architecture and control over data/dependencies. | verified; DOI checked; trust: high |
| SRC-ARCH-002 | Sandve, G. K.; Nekrutenko, A.; Taylor, J.; Hovig, E. Ten Simple Rules for Reproducible Computational Research. PLOS Computational Biology. | Peer-reviewed article | 2013 | DOI: 10.1371/journal.pcbi.1003285 | Reproducibility principles: artifacts, scripts, environment, traceability. | verified; PLOS DOI checked; trust: high |
| SRC-ARCH-003 | Boettiger, C. An Introduction to Docker for Reproducible Research. ACM SIGOPS Operating Systems Review. | Peer-reviewed article | 2015 | DOI: 10.1145/2723872.2723882 | Containerization as reproducibility support for research software. | needs verification; DOI/title checked, final pages/issue should be verified before ГОСТ finalization |
| SRC-ARCH-004 | Bass, L.; Clements, P.; Kazman, R. Software Architecture in Practice. 4th ed. Addison-Wesley Professional. | Book | 2021 | ISBN: 978-0-13-688609-9 | Layered/software architecture, maintainability and quality attributes. | verified; publisher/SEI metadata checked; trust: high |
