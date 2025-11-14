from models import AuditIssue, AuditResult

def run_all_checks(claim):
    issues = []
    score = 100
    for line in claim.lines:
        if line.units > 3:
            issues.append(AuditIssue(
                severity="warning",
                message="High units, please review.",
                line_numbers=[line.line_number]
            ))
            score -= 5
    return AuditResult(score=max(score,0), issues=issues)
