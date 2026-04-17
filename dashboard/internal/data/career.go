package data

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/santifer/career-ops/dashboard/internal/model"
)

// dashboardRow is the JSON schema written by
// scripts/db-write.mjs refresh-dashboard-json. Fields map 1:1 to applications
// joined with the latest_report row so the dashboard can render without a
// second trip to the DB.
type dashboardRow struct {
	ID                int     `json:"id"`
	Date              string  `json:"date"`
	Company           string  `json:"company"`
	Role              string  `json:"role"`
	Score             float64 `json:"score"`
	Status            string  `json:"status"`
	HasPDF            bool    `json:"has_pdf"`
	URL               string  `json:"url"`
	BatchID           string  `json:"batch_id"`
	Archetype         string  `json:"archetype"`
	TlDr              string  `json:"tldr"`
	Remote            string  `json:"remote"`
	Comp              string  `json:"comp"`
	Legitimacy        string  `json:"legitimacy"`
	Notes             string  `json:"notes"`
	ReportNum         *int    `json:"report_num"`
	ReportCompanySlug string  `json:"report_company_slug"`
	ReportDate        string  `json:"report_date"`
}

// dashboardJSONPath returns the expected location of the DuckDB snapshot.
func dashboardJSONPath(careerOpsPath string) string {
	return filepath.Join(careerOpsPath, "data", "dashboard.json")
}

// duckDBPath returns the expected location of the DuckDB file.
func duckDBPath(careerOpsPath string) string {
	return filepath.Join(careerOpsPath, "data", "career-ops.duckdb")
}

// ParseApplications reads data/dashboard.json (produced by
// scripts/db-write.mjs refresh-dashboard-json) and returns the tracker view.
// Returns nil when the snapshot is missing or unreadable so callers can surface
// a clear onboarding message.
func ParseApplications(careerOpsPath string) []model.CareerApplication {
	content, err := os.ReadFile(dashboardJSONPath(careerOpsPath))
	if err != nil {
		return nil
	}

	var rows []dashboardRow
	if err := json.Unmarshal(content, &rows); err != nil {
		fmt.Fprintf(os.Stderr, "WARN: dashboard.json unmarshal failed: %v\n", err)
		return nil
	}

	apps := make([]model.CareerApplication, 0, len(rows))
	for _, r := range rows {
		app := model.CareerApplication{
			Number:       r.ID,
			Date:         r.Date,
			Company:      r.Company,
			Role:         r.Role,
			Status:       r.Status,
			Score:        r.Score,
			ScoreRaw:     scoreDisplay(r.Score),
			HasPDF:       r.HasPDF,
			Notes:        r.Notes,
			JobURL:       r.URL,
			Archetype:    r.Archetype,
			TlDr:         r.TlDr,
			Remote:       r.Remote,
			CompEstimate: r.Comp,
		}
		if r.ReportNum != nil {
			app.ReportNumber = fmt.Sprintf("%03d", *r.ReportNum)
			// Prefer the exact slug + date stored in the DB; fall back to a
			// best-effort slug of the company name if the join column is
			// absent (older snapshot).
			slug := r.ReportCompanySlug
			if slug == "" {
				slug = slugify(r.Company)
			}
			date := r.ReportDate
			if date == "" {
				date = r.Date
			}
			app.ReportPath = filepath.Join(
				"reports",
				fmt.Sprintf("%s-%s-%s.md", app.ReportNumber, slug, date),
			)
		}
		apps = append(apps, app)
	}
	return apps
}

func scoreDisplay(score float64) string {
	if score == 0 {
		return ""
	}
	return fmt.Sprintf("%.1f/5", score)
}

// slugify reproduces the db-write.mjs report-filename slug so the dashboard can
// reconstruct the expected report path from (report_num, company, date).
func slugify(name string) string {
	s := strings.ToLower(strings.TrimSpace(name))
	var b strings.Builder
	for _, r := range s {
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
			b.WriteRune(r)
		case r == ' ', r == '-', r == '_', r == '.', r == '/':
			b.WriteRune('-')
		}
	}
	out := strings.Trim(b.String(), "-")
	for strings.Contains(out, "--") {
		out = strings.ReplaceAll(out, "--", "-")
	}
	return out
}

// LoadReportSummary returns the cached enrichment fields carried on the
// CareerApplication struct populated from dashboard.json. The pre-JSON
// implementation re-parsed the markdown file; that path is gone.
func LoadReportSummary(careerOpsPath, reportPath string) (archetype, tldr, remote, comp string) {
	apps := ParseApplications(careerOpsPath)
	for _, a := range apps {
		if a.ReportPath == reportPath {
			return a.Archetype, a.TlDr, a.Remote, a.CompEstimate
		}
	}
	return
}

// UpdateApplicationStatus shells out to `node scripts/db-write.mjs
// update-status` which acquires the lockfile, updates the row, and refreshes
// data/dashboard.json in a single Node invocation. This keeps the Go binary
// CGo-free without requiring the duckdb CLI to be on PATH.
func UpdateApplicationStatus(careerOpsPath string, app model.CareerApplication, newStatus string) error {
	if app.Number <= 0 {
		return fmt.Errorf("application has no id (Number=%d)", app.Number)
	}

	if _, err := os.Stat(duckDBPath(careerOpsPath)); err != nil {
		return fmt.Errorf("duckdb file missing: %w", err)
	}

	dbWrite := filepath.Join(careerOpsPath, "scripts", "db-write.mjs")
	cmd := exec.Command(
		"node", dbWrite, "update-status",
		fmt.Sprintf("--id=%d", app.Number),
		fmt.Sprintf("--status=%s", newStatus),
	)
	cmd.Dir = careerOpsPath
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("db-write update-status failed: %v: %s", err, strings.TrimSpace(string(out)))
	}
	return nil
}

// SnapshotFreshness reports whether data/dashboard.json is older than
// data/career-ops.duckdb. Intended for display in the status bar so the user
// can see when the snapshot has drifted from the DB.
func SnapshotFreshness(careerOpsPath string) (label string, stale bool) {
	snapInfo, snapErr := os.Stat(dashboardJSONPath(careerOpsPath))
	dbInfo, dbErr := os.Stat(duckDBPath(careerOpsPath))
	if snapErr != nil || dbErr != nil {
		return "snapshot: unknown", true
	}
	diff := dbInfo.ModTime().Sub(snapInfo.ModTime())
	if diff <= 0 {
		return fmt.Sprintf("snapshot: fresh (%s)", humanAge(time.Since(snapInfo.ModTime()))), false
	}
	return fmt.Sprintf("snapshot: stale by %s", humanAge(diff)), true
}

func humanAge(d time.Duration) string {
	if d < time.Minute {
		return fmt.Sprintf("%ds", int(d.Seconds()))
	}
	if d < time.Hour {
		return fmt.Sprintf("%dm", int(d.Minutes()))
	}
	if d < 24*time.Hour {
		return fmt.Sprintf("%dh", int(d.Hours()))
	}
	return fmt.Sprintf("%dd", int(d.Hours())/24)
}

// ComputeMetrics calculates aggregate stats from applications.
func ComputeMetrics(apps []model.CareerApplication) model.PipelineMetrics {
	m := model.PipelineMetrics{
		Total:    len(apps),
		ByStatus: make(map[string]int),
	}

	var totalScore float64
	var scored int

	for _, app := range apps {
		status := NormalizeStatus(app.Status)
		m.ByStatus[status]++

		if app.Score > 0 {
			totalScore += app.Score
			scored++
			if app.Score > m.TopScore {
				m.TopScore = app.Score
			}
		}
		if app.HasPDF {
			m.WithPDF++
		}
		if status != "skip" && status != "rejected" && status != "discarded" {
			m.Actionable++
		}
	}

	if scored > 0 {
		m.AvgScore = totalScore / float64(scored)
	}

	return m
}

// NormalizeStatus maps raw status text to a canonical form. The DuckDB ENUM
// already enforces canonical values, but legacy report bodies and hand-edited
// entries may still leak through -- keep the normalizer as a belt-and-braces.
// Aliases match states.yml.
func NormalizeStatus(raw string) string {
	s := strings.ReplaceAll(raw, "**", "")
	s = strings.TrimSpace(strings.ToLower(s))
	if idx := strings.Index(s, " 202"); idx > 0 {
		s = strings.TrimSpace(s[:idx])
	}

	switch {
	case s == "skip" || strings.Contains(s, "geo blocker"):
		return "skip"
	case strings.Contains(s, "interview"):
		return "interview"
	case s == "offer":
		return "offer"
	case strings.Contains(s, "responded"):
		return "responded"
	case strings.Contains(s, "applied") || s == "sent":
		return "applied"
	case strings.Contains(s, "rejected"):
		return "rejected"
	case strings.Contains(s, "discarded") || strings.HasPrefix(s, "dup"):
		return "discarded"
	case strings.Contains(s, "evaluated") || s == "hold" || s == "monitor":
		return "evaluated"
	default:
		return s
	}
}

// StatusPriority returns the sort priority for a status (lower = higher priority).
func StatusPriority(status string) int {
	switch NormalizeStatus(status) {
	case "interview":
		return 0
	case "offer":
		return 1
	case "responded":
		return 2
	case "applied":
		return 3
	case "evaluated":
		return 4
	case "skip":
		return 5
	case "rejected":
		return 6
	case "discarded":
		return 7
	default:
		return 8
	}
}
