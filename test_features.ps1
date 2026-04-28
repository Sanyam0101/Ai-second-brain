$base = 'http://localhost:8000/api/v1'
$errors = @()
$passed = @()

# 1. Register
Write-Host "=== 1. REGISTER ===" -ForegroundColor Cyan
$body = '{"email":"testbrain2@brainroot.dev","password":"TestPass123!"}'
try {
    $r = Invoke-WebRequest -Uri "$base/auth/register" -Method POST -Body $body -ContentType 'application/json' -UseBasicParsing -ErrorAction Stop
    $passed += "Auth: Register"
    Write-Host "PASS Register: $($r.Content)" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.Value__
    if ($code -eq 400) {
        $passed += "Auth: Register (user exists, ok)"
        Write-Host "PASS Register: user already exists (OK)" -ForegroundColor Yellow
    } else {
        $errors += "Auth: Register FAILED $($_.Exception.Message)"
        Write-Host "FAIL Register: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 2. Login (correct endpoint with JSON)
Write-Host "`n=== 2. LOGIN ===" -ForegroundColor Cyan
$body = '{"email":"testbrain2@brainroot.dev","password":"TestPass123!"}'
$TOKEN = ""
try {
    $r = Invoke-WebRequest -Uri "$base/auth/login" -Method POST -Body $body -ContentType 'application/json' -UseBasicParsing -ErrorAction Stop
    $TOKEN = ($r.Content | ConvertFrom-Json).access_token
    $passed += "Auth: Login"
    Write-Host "PASS Login: Got token (${TOKEN}.Substring(0,20))..." -ForegroundColor Green
} catch {
    $errors += "Auth: Login FAILED $($_.Exception.Message)"
    Write-Host "FAIL Login: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Response body: " $_.ErrorDetails.Message -ForegroundColor Red
}

if (-not $TOKEN) {
    Write-Host "Cannot continue without auth token." -ForegroundColor Red
    exit 1
}

$headers = @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json" }

# 3. Create Note 1
Write-Host "`n=== 3. CREATE NOTE ===" -ForegroundColor Cyan
$noteId = ""
try {
    $body = '{"content":"Machine learning is a subfield of AI that uses statistical techniques","tags":["ai","ml","test"]}'
    $r = Invoke-WebRequest -Uri "$base/notes/" -Method POST -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $note = $r.Content | ConvertFrom-Json
    $noteId = $note.id
    $passed += "Notes: Create"
    Write-Host "PASS Create Note: id=$noteId" -ForegroundColor Green
} catch {
    $errors += "Notes: Create FAILED $($_.Exception.Message)"
    Write-Host "FAIL Create Note: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Body: $($_.ErrorDetails.Message)" -ForegroundColor Red
}

# 4. Create Note 2
Write-Host "`n=== 4. CREATE NOTE 2 ===" -ForegroundColor Cyan
$noteId2 = ""
try {
    $body = '{"content":"Deep learning uses neural networks with many layers for feature extraction","tags":["deeplearning","ai","neural"]}'
    $r = Invoke-WebRequest -Uri "$base/notes/" -Method POST -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $note2 = $r.Content | ConvertFrom-Json
    $noteId2 = $note2.id
    $passed += "Notes: Create 2"
    Write-Host "PASS Create Note 2: id=$noteId2" -ForegroundColor Green
} catch {
    $errors += "Notes: Create 2 FAILED $($_.Exception.Message)"
    Write-Host "FAIL Create Note 2: $($_.Exception.Message)" -ForegroundColor Red
}

# 5. Get All Notes
Write-Host "`n=== 5. GET ALL NOTES ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/notes/" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $notes = $r.Content | ConvertFrom-Json
    $passed += "Notes: Get All ($($notes.Count) notes)"
    Write-Host "PASS Get Notes: $($notes.Count) notes found" -ForegroundColor Green
} catch {
    $errors += "Notes: Get All FAILED $($_.Exception.Message)"
    Write-Host "FAIL Get Notes: $($_.Exception.Message)" -ForegroundColor Red
}

# 6. Semantic Search
Write-Host "`n=== 6. SEMANTIC SEARCH ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/notes/search?q=machine+learning&limit=5" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $results = $r.Content | ConvertFrom-Json
    $passed += "Notes: Semantic Search ($($results.Count) results)"
    Write-Host "PASS Semantic Search: $($results.Count) results" -ForegroundColor Green
} catch {
    $errors += "Notes: Search FAILED $($_.Exception.Message)"
    Write-Host "FAIL Search: $($_.Exception.Message)" -ForegroundColor Red
}

# 7. Get Single Note
Write-Host "`n=== 7. GET SINGLE NOTE ===" -ForegroundColor Cyan
if ($noteId) {
    try {
        $r = Invoke-WebRequest -Uri "$base/notes/$noteId" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
        $passed += "Notes: Get By ID"
        Write-Host "PASS Get By ID: OK" -ForegroundColor Green
    } catch {
        $errors += "Notes: Get By ID FAILED $($_.Exception.Message)"
        Write-Host "FAIL Get By ID: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# 8. Update Note
Write-Host "`n=== 8. UPDATE NOTE ===" -ForegroundColor Cyan
if ($noteId) {
    try {
        $body = '{"content":"Updated: Machine learning enables computers to learn from data automatically","tags":["ai","ml","updated"]}'
        $r = Invoke-WebRequest -Uri "$base/notes/$noteId" -Method PUT -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
        $passed += "Notes: Update"
        Write-Host "PASS Update Note: OK" -ForegroundColor Green
    } catch {
        $errors += "Notes: Update FAILED $($_.Exception.Message)"
        Write-Host "FAIL Update Note: $($_.Exception.Message) | $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# 9. Graph - Get All
Write-Host "`n=== 9. KNOWLEDGE GRAPH ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/graph/all" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $g = $r.Content | ConvertFrom-Json
    $passed += "Graph: Get All ($($g.nodes.Count) nodes, $($g.edges.Count) edges)"
    Write-Host "PASS Graph: $($g.nodes.Count) nodes, $($g.edges.Count) edges" -ForegroundColor Green
} catch {
    $errors += "Graph: Get All FAILED $($_.Exception.Message)"
    Write-Host "FAIL Graph: $($_.Exception.Message)" -ForegroundColor Red
}

# 10. Graph - Link two notes
Write-Host "`n=== 10. GRAPH LINK NOTES ===" -ForegroundColor Cyan
if ($noteId -and $noteId2) {
    try {
        $body = "{`"src_id`":`"$noteId`",`"dst_id`":`"$noteId2`"}"
        $r = Invoke-WebRequest -Uri "$base/graph/link" -Method POST -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
        $passed += "Graph: Link Notes"
        Write-Host "PASS Graph Link: $($r.Content)" -ForegroundColor Green
    } catch {
        $errors += "Graph: Link FAILED $($_.Exception.Message)"
        Write-Host "FAIL Graph Link: $($_.Exception.Message) | $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# 11. Analytics Overview
Write-Host "`n=== 11. ANALYTICS OVERVIEW ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/analytics/overview" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $a = $r.Content | ConvertFrom-Json
    $passed += "Analytics: Overview"
    Write-Host "PASS Analytics: notes=$($a.system_stats.total_notes), ideas=$($a.system_stats.total_ideas), tags=$($a.system_stats.total_tags), connections=$($a.system_stats.total_connections)" -ForegroundColor Green
} catch {
    $errors += "Analytics: Overview FAILED $($_.Exception.Message)"
    Write-Host "FAIL Analytics: $($_.Exception.Message) | $($_.ErrorDetails.Message)" -ForegroundColor Red
}

# 12. Analytics Stats
Write-Host "`n=== 12. ANALYTICS QUICK STATS ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/analytics/stats" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $passed += "Analytics: Quick Stats"
    Write-Host "PASS Quick Stats: $($r.Content)" -ForegroundColor Green
} catch {
    $errors += "Analytics: Quick Stats FAILED $($_.Exception.Message)"
    Write-Host "FAIL Quick Stats: $($_.Exception.Message)" -ForegroundColor Red
}

# 13. Analyst Ask
Write-Host "`n=== 13. AI ANALYST ASK ===" -ForegroundColor Cyan
try {
    $body = '{"query":"What do I know about machine learning?","limit":5}'
    $r = Invoke-WebRequest -Uri "$base/analyst/ask" -Method POST -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $ans = $r.Content | ConvertFrom-Json
    $passed += "Analyst: Ask"
    $preview = $ans.answer.Substring(0, [Math]::Min(100, $ans.answer.Length))
    Write-Host "PASS Analyst: scanned=$($ans.total_notes_scanned), time=$($ans.processing_time_ms)ms" -ForegroundColor Green
    Write-Host "  Answer preview: $preview" -ForegroundColor Gray
} catch {
    $errors += "Analyst: Ask FAILED $($_.Exception.Message)"
    Write-Host "FAIL Analyst: $($_.Exception.Message) | $($_.ErrorDetails.Message)" -ForegroundColor Red
}

# 14. Analyst Stats
Write-Host "`n=== 14. ANALYST STATS ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/analyst/stats" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $s = $r.Content | ConvertFrom-Json
    $passed += "Analyst: Stats"
    Write-Host "PASS Analyst Stats: notes=$($s.total_notes), graph=$($s.graph | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    $errors += "Analyst: Stats FAILED $($_.Exception.Message)"
    Write-Host "FAIL Analyst Stats: $($_.Exception.Message)" -ForegroundColor Red
}

# 15. Connect Integration (Web Scraper)
Write-Host "`n=== 15. INTEGRATIONS: CONNECT WEB SCRAPER ===" -ForegroundColor Cyan
try {
    $body = '{"platform":"webscraper","access_token":"https://example.com"}'
    $r = Invoke-WebRequest -Uri "$base/integrations/connect" -Method POST -Body $body -ContentType 'application/json' -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $passed += "Integrations: WebScraper Connect"
    Write-Host "PASS WebScraper Connect: $($r.Content)" -ForegroundColor Green
} catch {
    $errors += "Integrations: WebScraper FAILED $($_.Exception.Message)"
    Write-Host "FAIL WebScraper: $($_.Exception.Message) | $($_.ErrorDetails.Message)" -ForegroundColor Red
}

# 16. Get Integrations
Write-Host "`n=== 16. GET INTEGRATIONS ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/integrations/" -Method GET -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
    $integrations = $r.Content | ConvertFrom-Json
    $passed += "Integrations: Get All ($($integrations.Count) integrations)"
    Write-Host "PASS Get Integrations: $($integrations.Count) integrations" -ForegroundColor Green
} catch {
    $errors += "Integrations: Get All FAILED $($_.Exception.Message)"
    Write-Host "FAIL Get Integrations: $($_.Exception.Message)" -ForegroundColor Red
}

# 17. GraphRAG Health
Write-Host "`n=== 17. GRAPHRAG HEALTH ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "$base/graphrag/health" -Method GET -UseBasicParsing -ErrorAction Stop
    $passed += "GraphRAG: Health"
    Write-Host "PASS GraphRAG Health: $($r.Content)" -ForegroundColor Green
} catch {
    $errors += "GraphRAG: Health FAILED $($_.Exception.Message)"
    Write-Host "FAIL GraphRAG: $($_.Exception.Message)" -ForegroundColor Red
}

# 18. Delete Note
Write-Host "`n=== 18. DELETE NOTE ===" -ForegroundColor Cyan
if ($noteId) {
    try {
        $r = Invoke-WebRequest -Uri "$base/notes/$noteId" -Method DELETE -Headers @{ Authorization = "Bearer $TOKEN" } -UseBasicParsing -ErrorAction Stop
        $passed += "Notes: Delete"
        Write-Host "PASS Delete Note: OK (204)" -ForegroundColor Green
    } catch {
        $code = $_.Exception.Response.StatusCode.Value__
        if ($code -eq 204) {
            $passed += "Notes: Delete"
            Write-Host "PASS Delete Note: OK (204)" -ForegroundColor Green
        } else {
            $errors += "Notes: Delete FAILED $($_.Exception.Message)"
            Write-Host "FAIL Delete Note: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# === SUMMARY ===
Write-Host "`n=============================================" -ForegroundColor White
Write-Host "FULL TEST SUMMARY" -ForegroundColor White
Write-Host "=============================================" -ForegroundColor White
Write-Host "PASSED ($($passed.Count)):" -ForegroundColor Green
$passed | ForEach-Object { Write-Host "  [PASS] $_" -ForegroundColor Green }

if ($errors.Count -gt 0) {
    Write-Host "`nFAILED ($($errors.Count)):" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  [FAIL] $_" -ForegroundColor Red }
} else {
    Write-Host "`nAll tests passed!" -ForegroundColor Green
}
Write-Host "=============================================" -ForegroundColor White
