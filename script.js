function analyzeCode() {
    const code = document.getElementById('codeInput').value;

    fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert("An error occurred: " + data.error);
            return;
        }

        const tokens = data.tokens || [];
        const syntaxErrors = data.syntaxErrors || [];
        const semanticErrors = data.semanticErrors || [];
        const intermediateCode = data.intermediateCode || [];

        document.getElementById('tokens').innerHTML =
            tokens.map(t => `${t.type}: ${t.value}`).join('<br>') || 'None';

        document.getElementById('syntaxErrors').innerHTML =
            syntaxErrors.length ? syntaxErrors.join('<br>') : 'None';

        document.getElementById('semanticErrors').innerHTML =
            semanticErrors.length ? semanticErrors.join('<br>') : 'None';

        document.getElementById('intermediateCode').innerHTML =
            intermediateCode.length ? intermediateCode.join('<br>') : 'None';
    })
    .catch(err => {
        alert("Failed to analyze: " + err.message);
    });
}
