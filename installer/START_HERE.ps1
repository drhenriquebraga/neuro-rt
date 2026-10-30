[CmdletBinding()]
param(
    [string]$SuiteRoot,
    [ValidateSet('prepare', 'offline')][string]$Mode,
    [string]$OutputFolder,
    [switch]$AcceptPreparationTerms,
    [string]$PreparationPolicyVersion,
    [string]$PreparationPolicySha256,
    [string]$ProgressFile,
    [string]$CancelFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-NeuroField($Value, [string]$Name, $Default = $null) {
    if ($null -eq $Value) { return $Default }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}
function ConvertTo-NeuroArgument([AllowEmptyString()][string]$Value) {
    # Windows CRT quoting; Python is launched directly, never through a shell.
    $quoted = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '$1$1')
    return '"' + $quoted + '"'
}
function Resolve-NeuroSuite([string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Root)) { throw 'Selecione a Local Suite instalada.' }
    $suite = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path
    foreach ($relative in @('python\python.exe', '.venv\Scripts\python.exe')) {
        $python = Join-Path $suite $relative
        if (Test-Path -LiteralPath $python -PathType Leaf) { return [pscustomobject]@{ Root=$suite; Python=$python } }
    }
    throw 'Selecione a Local Suite completa 8.12 ou posterior.'
}
function New-NeuroBackendArguments([string]$CodeRoot, [string]$Root, [string[]]$Options) {
    $entry = 'import sys; sys.path.insert(0, sys.argv.pop(1)); from neuro_rt.setup_wizard import main; sys.exit(main())'
    return @('-I', '-B', '-c', $entry, $CodeRoot, '--suite-root', $Root) + $Options
}
function Start-NeuroChild([string]$Python, [string[]]$Arguments, [string]$WorkingDirectory, [switch]$Interactive) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName=$Python; $info.WorkingDirectory=$WorkingDirectory
    $info.Arguments=(($Arguments | ForEach-Object { ConvertTo-NeuroArgument $_ }) -join ' ')
    $info.UseShellExecute=$false; $info.CreateNoWindow=$true
    $info.WindowStyle=[System.Diagnostics.ProcessWindowStyle]::Hidden
    $info.RedirectStandardOutput=-not $Interactive; $info.RedirectStandardError=-not $Interactive; $info.RedirectStandardInput=-not $Interactive
    if (-not $Interactive) {
        $info.StandardOutputEncoding=New-Object System.Text.UTF8Encoding($false)
        $info.StandardErrorEncoding=New-Object System.Text.UTF8Encoding($false)
    }
    $process=New-Object System.Diagnostics.Process; $process.StartInfo=$info
    if (-not $process.Start()) { throw 'Não foi possível iniciar o assistente.' }
    $outTask=$null;$errTask=$null
    if (-not $Interactive) {
        $process.StandardInput.Close()
        $outTask=$process.StandardOutput.ReadToEndAsync();$errTask=$process.StandardError.ReadToEndAsync()
    }
    return [pscustomobject]@{ Process=$process; OutTask=$outTask; ErrTask=$errTask }
}
function ConvertFrom-NeuroOutput([string]$Text) {
    $lines=@($Text -split [Environment]::NewLine | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    for ($i=$lines.Count-1; $i -ge 0; $i--) {
        try { $value=$lines[$i] | ConvertFrom-Json; if ($null -ne (Get-NeuroField $value 'state')) { return $value } } catch {}
    }
    throw 'O assistente terminou sem uma confirmação válida.'
}
function Get-NeuroCounter($Value,[string]$Name) {
    $raw=Get-NeuroField $Value $Name; $number=0L
    if ($null -ne $raw -and $raw -isnot [bool] -and [long]::TryParse([string]$raw,[ref]$number) -and $number -ge 0) { return $number }
    return $null
}
function Format-NeuroBytes([long]$Value) {
    $culture=[Globalization.CultureInfo]::GetCultureInfo('pt-BR')
    foreach ($unit in @(@('GB',1073741824L),@('MB',1048576L),@('KB',1024L))) {
        if ($Value -ge $unit[1]) { return ([double]$Value/$unit[1]).ToString('N1',$culture)+' '+$unit[0] }
    }
    return [string]$Value+' bytes'
}
function Set-NeuroProgress($Context,$Event) {
    $phase=[string](Get-NeuroField $Event 'resource_stage' (Get-NeuroField $Event 'stage' 'checking'))
    $labels=@{checking='Conferindo o pacote';preparing='Preparando recursos';resources='Preparando recursos'
        downloading='Baixando recurso';extracting='Extraindo recurso';validating='Conferindo a integridade'
        copying='Copiando arquivos verificados';complete='Concluindo e conferindo o pacote'}
    $label='Preparando o pacote'; if ($labels.ContainsKey($phase)) { $label=$labels[$phase] }
    $component=[string](Get-NeuroField $Event 'component' '')
    if ($component -match '^[A-Za-z0-9_.-]{1,160}$') { $label+=': '+$component }
    $parts=New-Object 'System.Collections.Generic.List[string]'; $parts.Add($label); $percent=0
    $done=Get-NeuroCounter $Event 'completed_files'; $total=Get-NeuroCounter $Event 'total_files'
    $bytes=Get-NeuroCounter $Event 'downloaded_bytes'; $size=Get-NeuroCounter $Event 'total_bytes'
    if ($null -eq $bytes) { $bytes=Get-NeuroCounter $Event 'processed_bytes'; $size=Get-NeuroCounter $Event 'total_unpacked_bytes' }
    if ($null -ne $done -and $null -ne $total -and $total -gt 0 -and $done -le $total) {
        $parts.Add([string]$done+' de '+[string]$total+' arquivos'); $percent=[int][math]::Floor(100.0*$done/$total)
    }
    if ($null -ne $bytes -and $null -ne $size -and $size -gt 0 -and $bytes -le $size) {
        $parts.Add((Format-NeuroBytes $bytes)+' de '+(Format-NeuroBytes $size)); $percent=[int][math]::Floor(100.0*$bytes/$size)
    }
    $Context.ProgressBar.Value=[math]::Min(99,[math]::Max(0,$percent))
    $Context.LastPhase=$parts -join ' · '
}
function Update-NeuroControls($Context) {
    $busy=$null -ne $Context.Job; $valid=$null -ne $Context.Policy -and $null -ne $Context.Suite
    $destination=$Context.OutputText.Text.Trim(); $newFolder=-not [string]::IsNullOrWhiteSpace($destination)
    if ($newFolder) { try { $newFolder=[IO.Path]::IsPathRooted($destination) -and -not (Test-Path -LiteralPath $destination) } catch { $newFolder=$false } }
    foreach ($control in @($Context.RootText,$Context.BrowseSuite,$Context.OutputText,$Context.BrowseOutput)) { $control.Enabled=-not $busy }
    $Context.Accepted.Enabled=-not $busy -and $valid
    $Context.PrepareButton.Enabled=-not $busy -and $valid
    $Context.OfflineButton.Enabled=-not $busy -and $valid -and $Context.Accepted.Checked -and $newFolder
    $Context.CancelButton.Enabled=$busy -and $Context.Kind -eq 'offline' -and -not $Context.CancelRequested
    foreach ($button in @($Context.PrepareButton,$Context.OfflineButton,$Context.CancelButton,$Context.BrowseSuite,$Context.BrowseOutput)) {
        if ($button.Enabled) {
            $button.BackColor=[Drawing.ColorTranslator]::FromHtml('#1764a8');$button.ForeColor=[Drawing.Color]::White;$button.Cursor=[Windows.Forms.Cursors]::Hand
        } else {
            $button.BackColor=[Drawing.ColorTranslator]::FromHtml('#dbe4ee');$button.ForeColor=[Drawing.ColorTranslator]::FromHtml('#506078');$button.Cursor=[Windows.Forms.Cursors]::Default
        }
    }
}
function Remove-NeuroJobFiles($Context) {
    if ($Context.TempFolder) {
        foreach ($file in @($Context.ProgressFile,$Context.CancelFile)) {
            try { if ($file -and [IO.File]::Exists($file)) { [IO.File]::Delete($file) } } catch {}
        }
        try { [IO.Directory]::Delete($Context.TempFolder,$false) } catch {}
    }
    $Context.TempFolder=$null
}
function Start-NeuroWizardAction($Context,[string]$Kind) {
    if ($null -ne $Context.Job) { return }
    if ($Kind -eq 'offline' -and (-not $Context.Accepted.Checked -or $null -eq $Context.Policy)) {
        $Context.ResultBox.Text='Leia os termos e marque o aceite antes de preparar o pacote offline.'; return
    }
    try {
        $suite=Resolve-NeuroSuite $Context.RootText.Text.Trim(); $options=@('--describe')
        if ($Kind -eq 'offline') {
            $destination=$Context.OutputText.Text.Trim()
            if (-not [IO.Path]::IsPathRooted($destination) -or (Test-Path -LiteralPath $destination)) { throw 'Escolha uma pasta NOVA para o pacote offline.' }
            $options=@('--mode','offline','--output',$destination,'--accept-preparation-terms',
                '--preparation-policy-version',[string]$Context.Policy.version,'--preparation-policy-sha256',[string]$Context.Policy.digest)
        } elseif ($Kind -eq 'prepare') { $options=@('--mode','prepare') }
        elseif ($Kind -ne 'describe') { throw 'Ação não reconhecida.' }
        $Context.TempFolder=Join-Path ([IO.Path]::GetTempPath()) ('NEURO_SETUP_'+[guid]::NewGuid().ToString('N'))
        [void][IO.Directory]::CreateDirectory($Context.TempFolder)
        $Context.ProgressFile=Join-Path $Context.TempFolder 'progress.json'; $Context.CancelFile=Join-Path $Context.TempFolder 'cancel.request'
        if ($Kind -ne 'describe') { $options+=@('--progress-file',$Context.ProgressFile,'--cancel-file',$Context.CancelFile) }
        $arguments=New-NeuroBackendArguments $Context.CodeRoot $suite.Root $options
        $Context.Kind=$Kind; $Context.Suite=$suite; $Context.CancelRequested=$false; $Context.StartedAt=[datetime]::UtcNow
        $Context.ProgressBar.Value=0; $Context.LastPhase='Conferindo a suíte e os termos'
        if ($Kind -eq 'prepare') { $Context.LastPhase='Abrindo as configurações da Local Suite' }
        if ($Kind -eq 'offline') { $Context.LastPhase='Iniciando o preparo do pacote offline' }
        $Context.ResultBox.Text=''; $Context.Job=& $Context.Launcher $suite.Python $arguments $Context.CodeRoot
    } catch {
        Remove-NeuroJobFiles $Context
        $Context.LastPhase='Não foi possível iniciar'
        $Context.ResultBox.Text='Confira a pasta da Local Suite completa 8.12 ou posterior e escolha uma pasta nova de destino.'
    }
    Update-NeuroControls $Context
}
function Request-NeuroCancel($Context) {
    if ($null -eq $Context.Job -or $Context.Kind -ne 'offline' -or $Context.CancelRequested) { return }
    try {
        [IO.File]::WriteAllText($Context.CancelFile,'cancel',(New-Object System.Text.UTF8Encoding($false)))
        $Context.CancelRequested=$true; $Context.LastPhase='Cancelamento solicitado; aguardando a etapa atual terminar'
    } catch { $Context.LastPhase='Não foi possível registrar o cancelamento. Aguarde a etapa atual.' }
    Update-NeuroControls $Context
}
function Complete-NeuroWizardJob($Context) {
    $job=$Context.Job
    try {
        $result=ConvertFrom-NeuroOutput $job.OutTask.Result; $state=[string](Get-NeuroField $result 'state' 'failed')
        if ($job.Process.ExitCode -ne 0 -or $state -eq 'failed') {
            $code=[string](Get-NeuroField $result 'error_code' 'PREPARATION_FAILED')
            if ($code -notmatch '^[A-Z0-9_]{1,80}$') { $code='PREPARATION_FAILED' }
            $reason=[string](Get-NeuroField $result 'reason' 'Não foi possível concluir. Confira a suíte, a origem do SETUP e a conexão.')
            if ($reason.Length -gt 600 -or $reason -match '(?i)[A-Z]:[\\/]|\\\\|[\x00-\x08]') { $reason='Não foi possível concluir. Confira a suíte, a origem do SETUP e a conexão.' }
            $Context.ResultBox.Text=$reason+[Environment]::NewLine+'Código: '+$code; $Context.LastPhase='Preparo não concluído'
            if ($code -eq 'CANCELLED') { $Context.LastPhase='Montagem cancelada; os dados existentes foram preservados' }
            if ($Context.Kind -eq 'describe') { $Context.Policy=$null; $Context.Suite=$null }
        } elseif ($Context.Kind -eq 'describe') {
            $policy=Get-NeuroField $result 'policy'; $digest=[string](Get-NeuroField $policy 'digest' ''); $version=[string](Get-NeuroField $policy 'version' '')
            if ($digest -notmatch '^[a-f0-9]{64}$' -or [string]::IsNullOrWhiteSpace($version)) { throw 'Termos incompletos.' }
            $Context.Policy=$policy; $Context.Accepted.Checked=$false
            $clauses=@(Get-NeuroField $policy 'clauses' @() | ForEach-Object { [string](Get-NeuroField $_ 'text' '') })
            $Context.TermsBox.Text=[string](Get-NeuroField $policy 'title' 'Termos NEURO RT')+' · versão '+$version+
                [Environment]::NewLine+[Environment]::NewLine+($clauses -join ([Environment]::NewLine+[Environment]::NewLine))
            $Context.LicensesBox.Text=[string](Get-NeuroField $result 'licenses' 'Licenças não informadas.')
            $Context.LastPhase='Suíte conferida · NEURO RT '+[string](Get-NeuroField $result 'version' '')
            $Context.ResultBox.Text='Escolha uma das ações abaixo. Para o pacote offline, leia os termos e marque o aceite.'
        } elseif ($Context.Kind -eq 'prepare' -and $state -in @('ready','settings_opened')) {
            $Context.ProgressBar.Value=100; $Context.LastPhase='Configurações da suíte abertas'
            $Context.ResultBox.Text='Continue em Configurações > NEURO RT na Local Suite. O instalador e o aceite de instalação são controlados pela própria suíte.'
        } elseif ($Context.Kind -eq 'offline' -and $state -eq 'ready') {
            $Context.ProgressBar.Value=100; $Context.LastPhase='Pacote offline pronto'
            $Context.ResultBox.Text='O pacote foi gravado na pasta escolhida. Na outra máquina, abra Configurações > NEURO RT da Local Suite e escolha essa pasta.'
        } else { throw 'Confirmação inesperada.' }
    } catch {
        $Context.LastPhase='Não foi possível confirmar a conclusão'
        $Context.ResultBox.Text='O assistente terminou sem uma confirmação válida. Os dados existentes foram preservados. Verifique a suíte e tente novamente.'
        if ($Context.Kind -eq 'describe') { $Context.Policy=$null; $Context.Suite=$null }
    } finally {
        $job.Process.Dispose(); $Context.Job=$null; Remove-NeuroJobFiles $Context; Update-NeuroControls $Context
    }
    $Context.StatusLabel.Text=$Context.LastPhase
    if ($Context.CloseWhenDone) { $Context.Form.Close() }
}
function Invoke-NeuroWizardTick($Context) {
    if ($null -eq $Context.Job) {
        if ($Context.PendingDescribe -and [datetime]::UtcNow -ge $Context.DescribeAt) {
            $Context.PendingDescribe=$false
            if (-not [string]::IsNullOrWhiteSpace($Context.RootText.Text)) { Start-NeuroWizardAction $Context 'describe' }
        }
        return
    }
    try {
        if ($Context.ProgressFile -and (Test-Path -LiteralPath $Context.ProgressFile -PathType Leaf)) {
            try {
                if ((Get-Item -LiteralPath $Context.ProgressFile).Length -le 32768) {
                    $event=[IO.File]::ReadAllText($Context.ProgressFile,[Text.Encoding]::UTF8) | ConvertFrom-Json
                    if (-not $Context.CancelRequested) { Set-NeuroProgress $Context $event }
                }
            } catch {} # A concurrent atomic replace is retried on the next tick.
        }
        $elapsed=[datetime]::UtcNow-$Context.StartedAt
        $Context.StatusLabel.Text=$Context.LastPhase+' · '+[string][int]$elapsed.TotalSeconds+' s'
        if ($Context.Job.Process.HasExited -and $Context.Job.OutTask.IsCompleted -and $Context.Job.ErrTask.IsCompleted) { Complete-NeuroWizardJob $Context }
    } catch { $Context.StatusLabel.Text='Aguardando a confirmação do assistente…' }
}
function New-NeuroWizard([string]$InitialSuiteRoot='', [string]$InitialOutputFolder='', [scriptblock]$Launcher) {
    Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
    [Windows.Forms.Application]::EnableVisualStyles()
    $form=New-Object Windows.Forms.Form; $form.Text='NEURO RT · Local Suite'
    $form.ClientSize=New-Object Drawing.Size(940,800); $form.MinimumSize=New-Object Drawing.Size(860,680)
    $form.StartPosition='CenterScreen'; $form.AutoScaleMode='Dpi'; $form.AutoScroll=$true
    $form.BackColor=[Drawing.ColorTranslator]::FromHtml('#f1f5fa'); $form.ForeColor=[Drawing.ColorTranslator]::FromHtml('#1b2c40')
    $form.Font=New-Object Drawing.Font('Segoe UI',10)
    $grid=New-Object Windows.Forms.TableLayoutPanel; $grid.Dock='Top'; $grid.AutoSize=$true; $grid.ColumnCount=1
    $grid.Padding=New-Object Windows.Forms.Padding(22); $form.Controls.Add($grid)
    function Add-NeuroRow($Control,[int]$Height) {
        $row=$grid.RowCount; $grid.RowCount++
        [void]$grid.RowStyles.Add((New-Object Windows.Forms.RowStyle([Windows.Forms.SizeType]::Absolute,$Height)))
        $Control.Dock='Fill'; $Control.Margin=New-Object Windows.Forms.Padding(0,0,0,8); $grid.Controls.Add($Control,0,$row)
    }
    function New-NeuroLabel([string]$Text) { $label=New-Object Windows.Forms.Label; $label.Text=$Text; return $label }
    function New-NeuroButton([string]$Text) {
        $button=New-Object Windows.Forms.Button; $button.Text=$Text; $button.FlatStyle='Flat'; $button.UseVisualStyleBackColor=$false
        $button.BackColor=[Drawing.ColorTranslator]::FromHtml('#1764a8'); $button.ForeColor=[Drawing.Color]::White
        $button.FlatAppearance.BorderSize=0; $button.Cursor=[Windows.Forms.Cursors]::Hand; return $button
    }
    $header=New-Object Windows.Forms.Panel; $header.Width=896; $title=New-NeuroLabel 'NEURO RT'
    $title.Font=New-Object Drawing.Font('Segoe UI Semibold',23,[Drawing.FontStyle]::Bold); $title.SetBounds(0,0,300,40)
    $subtitle=New-NeuroLabel 'Preparar na suíte instalada ou montar um pacote para transportar.'
    $subtitle.SetBounds(0,43,850,22); $subtitle.Anchor='Top, Left, Right'
    $header.Controls.AddRange(@($title,$subtitle)); Add-NeuroRow $header 78
    $suitePanel=New-Object Windows.Forms.Panel; $suitePanel.Width=896; $suiteLabel=New-NeuroLabel 'Pasta da Local Suite completa (8.12 ou posterior)'
    $suiteLabel.SetBounds(0,0,840,20)
    $rootText=New-Object Windows.Forms.TextBox; $rootText.SetBounds(0,25,745,28); $rootText.Anchor='Top, Left, Right'
    $browseSuite=New-NeuroButton 'Escolher…'; $browseSuite.SetBounds(755,23,138,32); $browseSuite.Anchor='Top, Right'
    $suitePanel.Controls.AddRange(@($suiteLabel,$rootText,$browseSuite)); Add-NeuroRow $suitePanel 70
    $tabs=New-Object Windows.Forms.TabControl
    $termsPage=New-Object Windows.Forms.TabPage; $termsPage.Text='Termo de preparo'
    $licensesPage=New-Object Windows.Forms.TabPage; $licensesPage.Text='Licenças dos recursos'
    $terms=New-Object Windows.Forms.TextBox; $licenses=New-Object Windows.Forms.TextBox
    foreach ($box in @($terms,$licenses)) {
        $box.Dock='Fill'; $box.Multiline=$true; $box.ReadOnly=$true; $box.ScrollBars='Vertical'; $box.WordWrap=$true
        $box.BorderStyle='FixedSingle'; $box.BackColor=[Drawing.Color]::White; $box.Font=New-Object Drawing.Font('Segoe UI',10)
    }
    $terms.Text='Selecione a suíte para carregar os termos e as licenças. Esta verificação não baixa recursos.'
    $termsPage.Controls.Add($terms); $licensesPage.Controls.Add($licenses); $tabs.TabPages.AddRange(@($termsPage,$licensesPage)); Add-NeuroRow $tabs 212
    $consentPanel=New-Object Windows.Forms.Panel; $consentPanel.Width=896; $accepted=New-Object Windows.Forms.CheckBox
    $accepted.Text='Li os termos e autorizo o preparo do pacote offline nesta máquina.'; $accepted.Checked=$false
    $accepted.SetBounds(0,0,870,25); $accepted.Anchor='Top, Left, Right'
    $separate=New-NeuroLabel 'Instalação e primeiro uso têm seus próprios aceites na Local Suite.'
    $separate.ForeColor=[Drawing.ColorTranslator]::FromHtml('#506078'); $separate.SetBounds(24,28,860,22)
    $consentPanel.Controls.AddRange(@($accepted,$separate)); Add-NeuroRow $consentPanel 64
    $outputPanel=New-Object Windows.Forms.Panel; $outputPanel.Width=896; $outputLabel=New-NeuroLabel 'Pasta NOVA para o pacote offline'
    $outputLabel.SetBounds(0,0,840,20)
    $outputText=New-Object Windows.Forms.TextBox; $outputText.SetBounds(0,25,745,28); $outputText.Anchor='Top, Left, Right'
    $browseOutput=New-NeuroButton 'Escolher local…'; $browseOutput.SetBounds(755,23,138,32); $browseOutput.Anchor='Top, Right'
    $outputPanel.Controls.AddRange(@($outputLabel,$outputText,$browseOutput)); Add-NeuroRow $outputPanel 70
    $actions=New-Object Windows.Forms.TableLayoutPanel; $actions.ColumnCount=2
    [void]$actions.ColumnStyles.Add((New-Object Windows.Forms.ColumnStyle([Windows.Forms.SizeType]::Percent,50)))
    [void]$actions.ColumnStyles.Add((New-Object Windows.Forms.ColumnStyle([Windows.Forms.SizeType]::Percent,50)))
    $prepare=New-NeuroButton 'Instalar/atualizar nesta suíte'; $offline=New-NeuroButton 'Montar pacote offline para transportar'
    $prepare.Dock='Fill'; $offline.Dock='Fill'; $prepare.Margin=New-Object Windows.Forms.Padding(0,0,6,0); $offline.Margin=New-Object Windows.Forms.Padding(6,0,0,0)
    $actions.Controls.Add($prepare,0,0); $actions.Controls.Add($offline,1,0); Add-NeuroRow $actions 56
    $progressPanel=New-Object Windows.Forms.Panel; $progressPanel.Width=896; $status=New-NeuroLabel 'Selecione a Local Suite instalada para começar.'
    $status.SetBounds(0,0,890,42); $status.Anchor='Top, Left, Right'
    $bar=New-Object Windows.Forms.ProgressBar; $bar.Style='Continuous'; $bar.SetBounds(0,47,735,15); $bar.Anchor='Top, Left, Right'
    $cancel=New-NeuroButton 'Cancelar preparo'; $cancel.SetBounds(755,40,138,30); $cancel.Anchor='Top, Right'
    $progressPanel.Controls.AddRange(@($status,$bar,$cancel)); Add-NeuroRow $progressPanel 84
    $resultBox=New-Object Windows.Forms.TextBox; $resultBox.Multiline=$true; $resultBox.ReadOnly=$true; $resultBox.ScrollBars='Vertical'; $resultBox.BackColor=[Drawing.Color]::White
    $resultBox.Text='A primeira ação abre as configurações da suíte. A segunda reúne os recursos licenciados para transportar.'; Add-NeuroRow $resultBox 78
    $rootText.AccessibleName='Pasta da Local Suite instalada';$outputText.AccessibleName='Nova pasta do pacote offline'
    $terms.AccessibleName='Termo de preparo';$licenses.AccessibleName='Licenças dos recursos';$bar.AccessibleName='Progresso da etapa atual'
    $context=[pscustomobject]@{
        Form=$form;RootText=$rootText;BrowseSuite=$browseSuite;OutputText=$outputText;BrowseOutput=$browseOutput
        Accepted=$accepted;PrepareButton=$prepare;OfflineButton=$offline;CancelButton=$cancel;TermsBox=$terms;LicensesBox=$licenses
        StatusLabel=$status;ProgressBar=$bar;ResultBox=$resultBox;CodeRoot=(Split-Path -Parent $PSScriptRoot);Launcher=$Launcher;Policy=$null;Suite=$null
        Job=$null;Kind='';TempFolder=$null;ProgressFile='';CancelFile='';StartedAt=[datetime]::UtcNow;CancelRequested=$false;LastPhase=''
        PendingDescribe=$false;DescribeAt=[datetime]::UtcNow;CloseWhenDone=$false;Timer=$null
    }
    if ($null -eq $context.Launcher) { $context.Launcher={param($Python,$Arguments,$WorkingDirectory) Start-NeuroChild $Python $Arguments $WorkingDirectory} }
    foreach ($control in @($form,$rootText,$browseSuite,$outputText,$browseOutput,$accepted,$prepare,$offline,$cancel)) { $control.Tag=$context }
    $rootText.Add_TextChanged({param($sender,$eventArgs)
        $ctx=$sender.Tag;$ctx.Policy=$null;$ctx.Suite=$null;$ctx.Accepted.Checked=$false;$ctx.PendingDescribe=$true;$ctx.DescribeAt=[datetime]::UtcNow.AddMilliseconds(600);Update-NeuroControls $ctx })
    $outputText.Add_TextChanged({param($sender,$eventArgs) Update-NeuroControls $sender.Tag})
    $accepted.Add_CheckedChanged({param($sender,$eventArgs) Update-NeuroControls $sender.Tag})
    $prepare.Add_Click({param($sender,$eventArgs) Start-NeuroWizardAction $sender.Tag 'prepare'})
    $offline.Add_Click({param($sender,$eventArgs) Start-NeuroWizardAction $sender.Tag 'offline'})
    $cancel.Add_Click({param($sender,$eventArgs) Request-NeuroCancel $sender.Tag})
    $browseSuite.Add_Click({param($sender,$eventArgs)
        $dialog=New-Object Windows.Forms.FolderBrowserDialog;$dialog.Description='Selecione a pasta da Local Suite completa 8.12 ou posterior.';$dialog.ShowNewFolderButton=$false
        try {if ($dialog.ShowDialog($sender.Tag.Form) -eq 'OK') {$sender.Tag.RootText.Text=$dialog.SelectedPath}} finally {$dialog.Dispose()} })
    $browseOutput.Add_Click({param($sender,$eventArgs)
        $dialog=New-Object Windows.Forms.FolderBrowserDialog;$dialog.Description='Escolha onde criar a NOVA pasta do pacote offline.';$dialog.ShowNewFolderButton=$false
        try {if ($dialog.ShowDialog($sender.Tag.Form) -eq 'OK') {$sender.Tag.OutputText.Text=Join-Path $dialog.SelectedPath ('NEURO_RT_OFFLINE_'+[datetime]::Now.ToString('yyyyMMdd_HHmmss'))}} finally {$dialog.Dispose()} })
    $form.Add_FormClosing({param($sender,$eventArgs)
        $ctx=$sender.Tag;if ($null -ne $ctx.Job) {$eventArgs.Cancel=$true;$ctx.CloseWhenDone=$true;Request-NeuroCancel $ctx;$ctx.StatusLabel.Text='Aguardando a operação terminar para fechar…'} })
    $timer=New-Object Windows.Forms.Timer;$timer.Interval=200;$timer.Add_Tick({Invoke-NeuroWizardTick $context}.GetNewClosure());$context.Timer=$timer
    $form.Add_FormClosed({param($sender,$eventArgs) $sender.Tag.Timer.Stop();$sender.Tag.Timer.Dispose()})
    $rootText.Text=$InitialSuiteRoot;$outputText.Text=$InitialOutputFolder;Update-NeuroControls $context;$timer.Start()
    return $context
}
if ($MyInvocation.InvocationName -ne '.') {
    try {
        if ($Mode) {
            $suite=Resolve-NeuroSuite $SuiteRoot;$codeRoot=Split-Path -Parent $PSScriptRoot;$options=@('--mode',$Mode)
            if ($OutputFolder) {$options+=@('--output',$OutputFolder)}
            if ($AcceptPreparationTerms) {$options+='--accept-preparation-terms'}
            if ($PreparationPolicyVersion) {$options+=@('--preparation-policy-version',$PreparationPolicyVersion)}
            if ($PreparationPolicySha256) {$options+=@('--preparation-policy-sha256',$PreparationPolicySha256)}
            if ($ProgressFile) {$options+=@('--progress-file',$ProgressFile)}
            if ($CancelFile) {$options+=@('--cancel-file',$CancelFile)}
            $child=Start-NeuroChild $suite.Python (New-NeuroBackendArguments $codeRoot $suite.Root $options) $codeRoot -Interactive
            $child.Process.WaitForExit()
            if ($child.Process.ExitCode) {[Console]::Error.WriteLine('O assistente não concluiu. Confira o diagnóstico acima.')}
            $result=$child.Process.ExitCode;$child.Process.Dispose();exit $result
        }
        $wizard=New-NeuroWizard -InitialSuiteRoot $SuiteRoot -InitialOutputFolder $OutputFolder
        [void]$wizard.Form.ShowDialog();$wizard.Form.Dispose();exit 0
    } catch {Write-Error 'Não foi possível abrir o assistente. Use a Local Suite completa 8.12 ou posterior.' -ErrorAction Continue;exit 1}
}
