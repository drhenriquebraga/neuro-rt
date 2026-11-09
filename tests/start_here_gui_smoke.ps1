param([Parameter(Mandatory=$true)][string]$ScriptPath)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. $ScriptPath
function Assert-Neuro($Condition,[string]$Message) {if (-not $Condition) {throw $Message}}
function Save-NeuroGuiImage($Context,[string]$Name) {
    $imageFolder=Join-Path $Context.CodeRoot 'runtime/test-tmp';[void][IO.Directory]::CreateDirectory($imageFolder)
    $image=New-Object Drawing.Bitmap($Context.Form.Width,$Context.Form.Height)
    try {$Context.Form.DrawToBitmap($image,(New-Object Drawing.Rectangle(0,0,$image.Width,$image.Height)));$image.Save((Join-Path $imageFolder $Name),[Drawing.Imaging.ImageFormat]::Png)} finally {$image.Dispose()}
}
$suiteRoot='C:/RADIOTERAPIA_AI/LOCAL_SUITE/_montagem/LOCAL_SUITE'
$suite=Resolve-NeuroSuite $suiteRoot
$policy=[pscustomobject]@{version='test-1';digest=('a'*64);title='Termo sintético';clauses=@([pscustomobject]@{text='Teste sem download e sem dados clínicos.'})}
$script:launched=New-Object 'System.Collections.Generic.List[object]'
$script:fakeJobs=New-Object 'System.Collections.Generic.List[object]'
function New-NeuroFakeJob([string]$Json,[bool]$Finished=$true,[int]$ExitCode=0) {
    $process=[pscustomobject]@{HasExited=$Finished;ExitCode=$ExitCode}
    $process | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
    return [pscustomobject]@{Process=$process;OutTask=[pscustomobject]@{IsCompleted=$Finished;Result=$Json};ErrTask=[pscustomobject]@{IsCompleted=$Finished;Result=''}}
}
$launcher={param($Python,$Arguments,$WorkingDirectory)
    $script:launched.Add([pscustomobject]@{Python=$Python;Arguments=$Arguments;WorkingDirectory=$WorkingDirectory})
    if ($Arguments -contains '--describe') {return New-NeuroFakeJob (([pscustomobject]@{state='ready';version='1.1.0';policy=$policy;licenses='Licença sintética MIT'})|ConvertTo-Json -Depth 6 -Compress)}
    $job=New-NeuroFakeJob '{"state":"ready","version":"1.1.0"}' $false
    $script:fakeJobs.Add($job);return $job
}
$context=$null
try {
    $context=New-NeuroWizard -InitialSuiteRoot $suiteRoot -InitialOutputFolder (Join-Path ([IO.Path]::GetTempPath()) ('NEURO_GUI_TEST_'+[guid]::NewGuid().ToString('N'))) -Launcher $launcher
    $context.Form.StartPosition='Manual';$context.Form.Location=New-Object Drawing.Point(-2500,-2500);$context.Form.ShowInTaskbar=$false
    $context.Form.Show();[Windows.Forms.Application]::DoEvents();$context.Timer.Stop();$context.PendingDescribe=$false
    foreach ($control in @($context.RootText,$context.BrowseSuite,$context.OutputText,$context.BrowseOutput,$context.CancelButton)) {
        Assert-Neuro ($control.Left -ge 0 -and $control.Right -le $control.Parent.ClientSize.Width) ('Control exceeds its panel: '+$control.GetType().Name)
    }
    Assert-Neuro (-not $context.Accepted.Checked) 'Consent must initially be unchecked.'
    Assert-Neuro (-not $context.OfflineButton.Enabled) 'Offline must be disabled before policy.'
    Start-NeuroWizardAction $context 'describe';Invoke-NeuroWizardTick $context
    Assert-Neuro ($null -ne $context.Policy) ('Policy not loaded: '+$context.ResultBox.Text)
    Assert-Neuro ($context.TermsBox.Text.Contains('Teste sem download')) 'Terms must be visible.'
    Assert-Neuro ($context.LicensesBox.Text.Contains('MIT')) 'Licenses must be visible.'
    Assert-Neuro ($context.PrepareButton.Enabled) 'Prepare should be available after Suite check.'
    Assert-Neuro (-not $context.OfflineButton.Enabled) 'Offline must remain disabled without consent.'
    $initialDestination=$context.OutputText.Text;$context.OutputText.Text='C:\Pacotes\NEURO_RT_OFFLINE'
    [Windows.Forms.Application]::DoEvents();Save-NeuroGuiImage $context 'start-here-gui.png';$context.OutputText.Text=$initialDestination
    $before=$script:launched.Count;Start-NeuroWizardAction $context 'offline'
    Assert-Neuro ($script:launched.Count -eq $before) 'No child/download before consent.'
    $context.Accepted.Checked=$true
    Assert-Neuro ($context.OfflineButton.Enabled) 'Offline should enable after explicit consent.'
    $context.OfflineButton.PerformClick();[Windows.Forms.Application]::DoEvents()
    Assert-Neuro ($null -ne $context.Job) ('Offline click did not start: '+$context.ResultBox.Text)
    $argsSent=$script:launched[$script:launched.Count-1].Arguments
    Assert-Neuro ($argsSent -contains '--accept-preparation-terms') 'Consent flag missing.'
    Assert-Neuro ($argsSent -contains $policy.digest) 'Exact accepted policy digest missing.'
    Assert-Neuro ($script:launched[$script:launched.Count-1].Python -eq $suite.Python) 'A different interpreter was selected.'
    Assert-Neuro (-not $context.RootText.Enabled -and $context.CancelButton.Enabled) 'Busy controls are inconsistent.'
    [IO.File]::WriteAllText($context.ProgressFile,'{"state":"preparing","stage":"resources","resource_stage":"downloading","component":"fixture.whl","downloaded_bytes":1048576,"total_bytes":2097152,"completed_files":2,"total_files":4}',(New-Object Text.UTF8Encoding($false)))
    $context.Timer.Start();$until=[datetime]::UtcNow.AddMilliseconds(450)
    while ([datetime]::UtcNow -lt $until) {[Windows.Forms.Application]::DoEvents();Start-Sleep -Milliseconds 15}
    $context.Timer.Stop()
    $clock=[Diagnostics.Stopwatch]::StartNew();Invoke-NeuroWizardTick $context;$clock.Stop()
    Assert-Neuro ($clock.ElapsedMilliseconds -lt 500) 'UI polling blocked.'
    Assert-Neuro ($context.StatusLabel.Text.Contains('2 de 4 arquivos') -and $context.StatusLabel.Text.Contains('MB')) 'Progress counters are not visible.'
    Assert-Neuro ($context.ProgressBar.Value -eq 50) 'Progress percentage is invalid.'
    Set-NeuroProgress $context ([pscustomobject]@{stage='complete';completed_files=4;total_files=4})
    Assert-Neuro ($context.ProgressBar.Value -lt 100) 'Progress events must not claim final success.'
    $context.CancelButton.PerformClick()
    Assert-Neuro ([IO.File]::Exists($context.CancelFile)) 'Cooperative cancel file was not written.'
    Assert-Neuro ($null -ne $context.Job -and -not $context.CancelButton.Enabled) 'Cancel must await the child.'
    $context.Job.OutTask.Result='{"state":"failed","error_code":"CANCELLED","reason":"Montagem cancelada."}'
    $context.Job.Process.HasExited=$true;$context.Job.Process.ExitCode=1;$context.Job.OutTask.IsCompleted=$true;$context.Job.ErrTask.IsCompleted=$true
    Invoke-NeuroWizardTick $context
    Assert-Neuro ($null -eq $context.Job -and $context.ResultBox.Text.Contains('CANCELLED')) 'Cancellation result must remain visible.'
    $context.PrepareButton.PerformClick();[Windows.Forms.Application]::DoEvents()
    $last=$script:launched[$script:launched.Count-1].Arguments
    Assert-Neuro ($last -contains 'prepare' -and -not ($last -contains '--accept-preparation-terms')) 'Prepare must only open host settings.'
    $context.Job.OutTask.Result='{"state":"settings_opened","stage":"complete"}';$context.Job.Process.HasExited=$true;$context.Job.OutTask.IsCompleted=$true;$context.Job.ErrTask.IsCompleted=$true
    Invoke-NeuroWizardTick $context
    Assert-Neuro ($context.StatusLabel.Text.Contains('Configurações') -and $context.ProgressBar.Value -eq 100) 'Prepare result is wrong.'
    $chosen=$context.OutputText.Text;$context.OutputText.Text=[IO.Path]::GetTempPath()
    Assert-Neuro (-not $context.OfflineButton.Enabled) 'An existing destination must not be offered.'
    $context.OutputText.Text=$chosen
    Set-NeuroProgress $context ([pscustomobject]@{stage='resources';component='C:\DO_NOT_SHOW\private.dcm';completed_files=8;total_files=2})
    Assert-Neuro ($context.ProgressBar.Value -eq 0 -and -not $context.LastPhase.Contains('DO_NOT_SHOW')) 'Invalid counters or private paths leaked.'
    # Exercise the real ProcessStartInfo quoting and asynchronous readers, using
    # only a synthetic JSON echo in the SAME existing Suite interpreter.
    $payload=@('espaço e ação','quote"slash\','trailing\','',"dollar`$literal")
    $entry='import json,sys,time;print(json.dumps(sys.argv[1:],ensure_ascii=True),flush=True);time.sleep(.2)'
    $real=Start-NeuroChild $suite.Python (@('-I','-B','-c',$entry)+$payload) $suite.Root
    $deadline=[datetime]::UtcNow.AddSeconds(15)
    while (-not ($real.Process.HasExited -and $real.OutTask.IsCompleted -and $real.ErrTask.IsCompleted)) {
        if ([datetime]::UtcNow -gt $deadline) {throw 'Synthetic child timeout.'};[Windows.Forms.Application]::DoEvents();Start-Sleep -Milliseconds 20
    }
    Assert-Neuro ($real.Process.ExitCode -eq 0) 'Synthetic child failed.'
    $echo=$real.OutTask.Result | ConvertFrom-Json
    Assert-Neuro ($echo.Count -eq $payload.Count) ('Argument count was changed: '+$real.OutTask.Result+' / '+$real.Process.StartInfo.Arguments)
    for ($i=0;$i -lt $payload.Count;$i++) {Assert-Neuro ($echo[$i] -ceq $payload[$i]) ('Quoting failed at argument '+$i)}
    $real.Process.Dispose()
    $interactive=Start-NeuroChild $suite.Python @('-I','-B','-c','print("NEURO_INTERACTIVE_STREAM=OK",flush=True)') $suite.Root -Interactive
    $interactive.Process.WaitForExit()
    Assert-Neuro (-not $interactive.Process.StartInfo.RedirectStandardOutput -and -not $interactive.Process.StartInfo.RedirectStandardInput -and $null -eq $interactive.OutTask) 'CLI prompts/output must inherit their console.'
    $interactive.Process.Dispose()
    $context.OfflineButton.PerformClick()
    $context.Job.OutTask.Result='{"state":"failed","error_code":"PACKAGE_INTEGRITY","reason":"C:\\DO_NOT_SHOW\\private.dcm"}'
    $context.Job.ErrTask.Result='C:\DO_NOT_SHOW\private.dcm';$context.Job.Process.HasExited=$true;$context.Job.Process.ExitCode=1;$context.Job.OutTask.IsCompleted=$true;$context.Job.ErrTask.IsCompleted=$true
    Invoke-NeuroWizardTick $context
    Assert-Neuro ($context.ResultBox.Text.Contains('PACKAGE_INTEGRITY') -and -not $context.ResultBox.Text.Contains('DO_NOT_SHOW')) 'Failure must persist without raw private paths.'
    $context.Form.ClientSize=New-Object Drawing.Size(860,680);[Windows.Forms.Application]::DoEvents()
    foreach ($control in @($context.RootText,$context.BrowseSuite,$context.OutputText,$context.BrowseOutput,$context.CancelButton)) {
        Assert-Neuro ($control.Left -ge 0 -and $control.Right -le $control.Parent.ClientSize.Width) 'A control was clipped after resizing.'
    }
    $context.Form.ClientSize=New-Object Drawing.Size(940,800);$context.OutputText.Text='C:\Pacotes\NEURO_RT_OFFLINE'
    [Windows.Forms.Application]::DoEvents()
    Save-NeuroGuiImage $context 'start-here-gui-complete.png'
    $context.OutputText.Text=$chosen;$context.OfflineButton.PerformClick()
    $context.Form.Close()
    Assert-Neuro (-not $context.Form.IsDisposed -and $null -ne $context.Job -and $context.CloseWhenDone) 'Closing must wait for the child.'
    Assert-Neuro ([IO.File]::Exists($context.CancelFile)) 'Closing must request cooperative cancellation.'
    $context.Job.OutTask.Result='{"state":"failed","error_code":"CANCELLED","reason":"Montagem cancelada."}'
    $context.Job.Process.HasExited=$true;$context.Job.Process.ExitCode=1;$context.Job.OutTask.IsCompleted=$true;$context.Job.ErrTask.IsCompleted=$true
    Invoke-NeuroWizardTick $context
    Assert-Neuro ($context.Form.IsDisposed) 'The window did not close after the child finished.'
    # One real backend action: describe only, no download/install/inference.
    $live=New-NeuroWizard -InitialSuiteRoot $suiteRoot
    try {
        $live.Timer.Stop();$live.PendingDescribe=$false
        Start-NeuroWizardAction $live 'describe'
        $until=[datetime]::UtcNow.AddSeconds(30)
        while ($null -ne $live.Job) {
            if ([datetime]::UtcNow -gt $until) {throw 'Read-only describe timeout.'}
            Invoke-NeuroWizardTick $live;[Windows.Forms.Application]::DoEvents();Start-Sleep -Milliseconds 20
        }
        Assert-Neuro ($null -ne $live.Policy -and $live.TermsBox.Text.Contains('NEURO RT')) ('Real describe failed: '+$live.ResultBox.Text)
        Assert-Neuro ($live.LicensesBox.Text.Length -gt 100 -and -not $live.Accepted.Checked) 'Real licenses/unchecked consent were not loaded.'
    } finally {$live.Timer.Stop();$live.Timer.Dispose();$live.Form.Dispose()}
    Write-Output 'NEURO_GUI_SMOKE=OK'
} finally {
    if ($null -ne $context) {
        if ($null -ne $context.Job) {$context.Job.Process.HasExited=$true;$context.Job.OutTask.IsCompleted=$true;$context.Job.ErrTask.IsCompleted=$true;Invoke-NeuroWizardTick $context}
        if (-not $context.Form.IsDisposed) {$context.Timer.Stop();$context.Form.Close();$context.Form.Dispose()}
    }
}
