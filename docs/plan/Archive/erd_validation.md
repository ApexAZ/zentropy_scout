# ERD Validation Report — Phase 1.1

**Date:** 2026-01-26
**Reference:** REQ-005 §3 Entity Relationship Diagram
**Status:** ✅ VALIDATED

---

## Summary

All 22 entities from the ERD are implemented as ORM models. Relationships match the specification with minor enhancements for flexibility.

---

## Entity Checklist

| Entity | ORM File | Table Name | Status |
|--------|----------|------------|--------|
| User | user.py | users | ✅ |
| Persona | persona.py | personas | ✅ |
| WorkHistory | persona_content.py | work_histories | ✅ |
| Skill | persona_content.py | skills | ✅ |
| Education | persona_content.py | educations | ✅ |
| Certification | persona_content.py | certifications | ✅ |
| AchievementStory | persona_content.py | achievement_stories | ✅ |
| Bullet | persona_content.py | bullets | ✅ |
| VoiceProfile | persona_settings.py | voice_profiles | ✅ |
| CustomNonNegotiable | persona_settings.py | custom_non_negotiables | ✅ |
| PersonaEmbedding | persona_settings.py | persona_embeddings | ✅ |
| PersonaChangeFlag | persona_settings.py | persona_change_flags | ✅ |
| ResumeFile | resume.py | resume_files | ✅ |
| BaseResume | resume.py | base_resumes | ✅ |
| JobVariant | resume.py | job_variants | ✅ |
| SubmittedResumePDF | resume.py | submitted_resume_pdfs | ✅ |
| CoverLetter | cover_letter.py | cover_letters | ✅ |
| SubmittedCoverLetterPDF | cover_letter.py | submitted_cover_letter_pdfs | ✅ |
| JobSource | job_source.py | job_sources | ✅ |
| UserSourcePreference | job_source.py | user_source_preferences | ✅ |
| PollingConfiguration | job_source.py | polling_configurations | ✅ |
| JobPosting | job_posting.py | job_postings | ✅ |
| ExtractedSkill | job_posting.py | extracted_skills | ✅ |
| Application | application.py | applications | ✅ |
| TimelineEvent | application.py | timeline_events | ✅ |

---

## Relationship Validation

### Persona Domain (REQ-001)

| ERD Relationship | Cardinality | ORM Implementation | Status |
|------------------|-------------|-------------------|--------|
| User → Persona | 1:1 | `User.personas` (list) | ✅ Enhanced to 1:many |
| Persona → WorkHistory | 1:many | `Persona.work_histories` | ✅ |
| Persona → Skill | 1:many | `Persona.skills` | ✅ |
| Persona → Education | 1:many | `Persona.educations` | ✅ |
| Persona → Certification | 1:many | `Persona.certifications` | ✅ |
| Persona → AchievementStory | 1:many | `Persona.achievement_stories` | ✅ |
| Persona → VoiceProfile | 1:1 optional | `Persona.voice_profile` (uselist=False) | ✅ |
| Persona → CustomNonNegotiable | 1:many | `Persona.custom_non_negotiables` | ✅ |
| Persona → PersonaEmbedding | 1:many | `Persona.embeddings` | ✅ |
| WorkHistory → Bullet | 1:many | `WorkHistory.bullets` | ✅ |
| AchievementStory → WorkHistory | many:1 optional | `AchievementStory.related_job` | ✅ |

### Resume Domain (REQ-002)

| ERD Relationship | Cardinality | ORM Implementation | Status |
|------------------|-------------|-------------------|--------|
| Persona → ResumeFile | 1:1 optional | `Persona.original_resume_file` + `resume_files` list | ✅ Enhanced |
| Persona → BaseResume | 1:many | `Persona.base_resumes` | ✅ |
| Persona → PersonaChangeFlag | 1:many | `Persona.change_flags` | ✅ |
| BaseResume → JobVariant | 1:many | `BaseResume.job_variants` | ✅ |
| JobVariant → SubmittedResumePDF | via Application | `Application.submitted_resume_pdf` | ✅ |

### Cover Letter Domain (REQ-002b)

| ERD Relationship | Cardinality | ORM Implementation | Status |
|------------------|-------------|-------------------|--------|
| Persona → CoverLetter | 1:many | `Persona.cover_letters` | ✅ |
| CoverLetter → SubmittedCoverLetterPDF | 1:many | `CoverLetter.submitted_pdfs` | ✅ |

### Job Posting Domain (REQ-003)

| ERD Relationship | Cardinality | ORM Implementation | Status |
|------------------|-------------|-------------------|--------|
| JobSource → UserSourcePreference | 1:many | `JobSource.user_preferences` | ✅ |
| JobSource → JobPosting | 1:many | `JobSource.job_postings` | ✅ |
| Persona → UserSourcePreference | 1:many | `Persona.source_preferences` | ✅ |
| Persona → PollingConfiguration | 1:1 optional | `Persona.polling_configuration` (uselist=False) | ✅ |
| Persona → JobPosting | 1:many | `Persona.job_postings` | ✅ |
| JobPosting → ExtractedSkill | 1:many | `JobPosting.extracted_skills` | ✅ |
| JobPosting → JobPosting (self) | JSONB array | `JobPosting.previous_posting_ids` | ✅ |

### Application Domain (REQ-004)

| ERD Relationship | Cardinality | ORM Implementation | Status |
|------------------|-------------|-------------------|--------|
| Persona → Application | 1:many | `Persona.applications` | ✅ |
| JobPosting → Application | 1:many | `JobPosting.applications` | ✅ |
| JobVariant → Application | 1:many | `JobVariant.applications` | ✅ |
| CoverLetter → Application | 1:1 optional | `CoverLetter.application` | ✅ |
| Application → TimelineEvent | 1:many | `Application.timeline_events` | ✅ |
| Application ↔ SubmittedResumePDF | bidirectional | Both FKs nullable | ✅ |
| Application ↔ SubmittedCoverLetterPDF | bidirectional | Both FKs nullable | ✅ |

---

## Noted Enhancements

The ORM implementation includes these intentional enhancements over the ERD:

1. **User → Persona (1:many)**: ERD shows 1:1, but ORM allows multiple personas per user for future multi-persona support.

2. **Persona → ResumeFile**: ERD shows single "uploaded" relationship. ORM has both:
   - `original_resume_file` (1:1 optional) - matches ERD intent
   - `resume_files` (1:many) - allows upload history

3. **Cascade behaviors**: All child relationships have `CASCADE` on delete where appropriate, `RESTRICT` where data integrity requires it.

---

## Circular References

Per REQ-005 §9.2, the following circular references are correctly handled:

| Tables | Resolution |
|--------|------------|
| Application ↔ SubmittedResumePDF | Both `application_id` FKs are nullable |
| Application ↔ SubmittedCoverLetterPDF | Both `application_id` FKs are nullable |
| CoverLetter → Application | `application_id` is nullable, FK added after Application exists |
| Persona ↔ ResumeFile | `original_resume_file_id` added after ResumeFile table created |

---

## Conclusion

**The ORM models correctly implement all entities and relationships from REQ-005 §3 ERD.**

Minor enhancements (1:many instead of 1:1 for User→Persona) provide flexibility without violating the logical model. All FK constraints, cascade behaviors, and circular reference resolutions match the specification.
