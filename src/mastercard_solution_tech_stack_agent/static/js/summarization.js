document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const session = urlParams.get('sessionid');
    let apiUrl = 'http://localhost:8000/api/v1/conversation_summary';

    console.log("session id", session)
    if (session) {
        apiUrl += `?session_id=${session}`;

        fetch(apiUrl)
            .then(response => {
                // console.log("response", response)
                return response.json()})
            .then(data => {
                const contentDiv = document.getElementById('summary');
                if (contentDiv) {
                    let html = '';
                    if (data.status !== 200) {
                        console.error('Error fetching data:', data.statusText);
                        html += data["content"]
                        contentDiv.innerHTML = html;
                    }
                    else {
                        html += data["summary"]
                        contentDiv.innerHTML = html;
                    }
                } else {    
                    console.error('Element with id "content" not found.');
                }
            })
            .catch(error => console.error('Error fetching data:', error));
    }
});
