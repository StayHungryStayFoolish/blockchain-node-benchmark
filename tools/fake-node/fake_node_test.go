package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestSourceDirReturnsAbsolutePath verifies sourceDir returns the absolute
// directory containing fake_node.go during tests.
func TestSourceDirReturnsAbsolutePath(t *testing.T) {
	got := sourceDir()
	if got == "" {
		t.Fatal("sourceDir() returned empty string; runtime.Caller failed unexpectedly")
	}
	if !filepath.IsAbs(got) {
		t.Errorf("sourceDir() = %q; want absolute path", got)
	}
	// fake_node.go lives beside this test file.
	if _, err := os.Stat(filepath.Join(got, "fake_node.go")); err != nil {
		t.Errorf("sourceDir()=%q does not contain fake_node.go: %v", got, err)
	}
}

// TestExecutableDirReturnsAbsolutePath verifies executableDir behavior.
// go test builds the test binary in a temp directory, which should be returned.
func TestExecutableDirReturnsAbsolutePath(t *testing.T) {
	got := executableDir()
	if got == "" {
		t.Fatal("executableDir() returned empty; os.Executable failed")
	}
	if !filepath.IsAbs(got) {
		t.Errorf("executableDir() = %q; want absolute path", got)
	}
}

// TestDefaultChainsDirResolvesToRepoChains verifies the default chains path
// resolves to repo config/chains regardless of cwd.
func TestDefaultChainsDirResolvesToRepoChains(t *testing.T) {
	// Temporarily switch to an unrelated cwd to prove resolution is cwd-independent.
	tmp := t.TempDir()
	origCwd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(origCwd)
	if err := os.Chdir(tmp); err != nil {
		t.Fatal(err)
	}

	got := defaultChainsDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultChainsDir()=%q; want absolute path resolved from binary/source location", got)
	}
	solanaJSON := filepath.Join(got, "solana.json")
	if _, err := os.Stat(solanaJSON); err != nil {
		t.Errorf("defaultChainsDir()=%q missing expected solana.json: %v", got, err)
	}
	if !strings.HasSuffix(filepath.ToSlash(got), "config/chains") {
		t.Errorf("defaultChainsDir()=%q; expected suffix config/chains", got)
	}
}

// TestDefaultConfigsDirResolvesToFakeNodeConfigs verifies the default configs path.
func TestDefaultConfigsDirResolvesToFakeNodeConfigs(t *testing.T) {
	tmp := t.TempDir()
	origCwd, _ := os.Getwd()
	defer os.Chdir(origCwd)
	os.Chdir(tmp)

	got := defaultConfigsDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultConfigsDir()=%q; want absolute path", got)
	}
	if _, err := os.Stat(filepath.Join(got, "jsonrpc.yaml")); err != nil {
		t.Errorf("defaultConfigsDir()=%q missing jsonrpc.yaml: %v", got, err)
	}
}

// TestDefaultFixturesDirResolvesToFakeNodeFixtures verifies the default fixtures path.
func TestDefaultFixturesDirResolvesToFakeNodeFixtures(t *testing.T) {
	tmp := t.TempDir()
	origCwd, _ := os.Getwd()
	defer os.Chdir(origCwd)
	os.Chdir(tmp)

	got := defaultFixturesDir()
	if !filepath.IsAbs(got) {
		t.Fatalf("defaultFixturesDir()=%q; want absolute path", got)
	}
	if _, err := os.Stat(filepath.Join(got, "solana")); err != nil {
		t.Errorf("defaultFixturesDir()=%q missing solana/ subdir: %v", got, err)
	}
}

// TestResolveDefaultPathFallback verifies fallback behavior when neither
// source-relative nor executable-relative resources exist.
func TestResolveDefaultPathFallback(t *testing.T) {
	// Use a definitely missing subdirectory so both lookup locations fail.
	const bogus = "__definitely_not_a_real_dir_xyzzy__"
	const fallback = "FALLBACK_RELATIVE_PATH"
	got := resolveDefaultPath(bogus, bogus, fallback)
	if got != fallback {
		t.Errorf("resolveDefaultPath(bogus, bogus, %q) = %q; want fallback", fallback, got)
	}
}

// TestResolveDefaultPathPrefersExecutableDirWhenSourceMissing verifies the
// executable-relative fallback path.
func TestResolveDefaultPathPrefersExecutableDirWhenSourceMissing(t *testing.T) {
	exeDir := executableDir()
	if exeDir == "" {
		t.Skip("executableDir unavailable")
	}
	// Create a real subdirectory beside the test binary.
	marker := filepath.Join(exeDir, "fake_node_test_marker")
	if err := os.MkdirAll(marker, 0o755); err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(marker)

	got := resolveDefaultPath(
		"__no_such_source_rel__",
		"fake_node_test_marker",
		"FALLBACK",
	)
	if got != marker {
		t.Errorf("resolveDefaultPath returned %q; want exe-relative %q", got, marker)
	}
}
