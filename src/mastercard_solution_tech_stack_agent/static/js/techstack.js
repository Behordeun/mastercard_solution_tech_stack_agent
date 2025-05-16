document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const session = urlParams.get('sessionid');
    let apiUrl = 'http://localhost:8000/api/v1/recommeded_stack';
    
    if (session) {
        apiUrl += `?session_id=${session}`;
    }

    fetch(apiUrl)
        .then(response => response.json())
        .then(data => {
            const contentDiv = document.getElementById('content');

            if (contentDiv) {
                let html = '';
                if (data.status === 200) {
                    for (const category in data.content) {
                        if (data.content.hasOwnProperty(category)) {
                            html += `<h2>${category}</h2>`;
                            html += '<h3>Top Recommendation</h3>';
                            html += `<p><strong>Tech Stack:</strong> ${data.content[category].top_recommendation["tech stack"] || data.content[category].top_recommendation["technology"]}</p>`;
                            html += `<p><strong>Use Case:</strong> ${data.content[category].top_recommendation.use_case}</p>`;

                            html += '<h3>Alternative</h3>';
                            html += `<p><strong>Technology:</strong> ${data.content[category].alternative.technology}</p>`;
                            html += `<p><strong>Use Case:</strong> ${data.content[category].alternative.use_case}</p>`;
                        }
                    }
                    contentDiv.innerHTML = html;

                } else {
                    html += data["content"]
                    contentDiv.innerHTML = html;
                }
            } else {
                console.error('Element with id "content" not found.');
            }
        })
        .catch(error => console.error('Error fetching data:', error));
});
