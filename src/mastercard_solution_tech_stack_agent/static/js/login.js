
document.getElementById('loginForm').addEventListener('submit', function (e) {
    e.preventDefault();
    handleLogin();
});

async function handleLogin() {
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value.trim();

  try {
    const response = await fetch('/api/v1/users/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: email,
        password: password,
      })
    });

    console.log("Response:", response);
    
    // if (!response.ok) {
    //   document.getElementById('error-msg').textContent = 'There was an error processing your request. Please try again later.';
    // }

    if (response.status === 400) {
      const errorData = await response.json();
      console.error("❌ Error Data", errorData['detail']);
      document.getElementById('error-msg').textContent = errorData.message || 'Invalid input. Please check your data.';
      return;
    }
    if (response.status === 422){
      const errorData = await response.json();
      console.error("❌ Error Data", errorData);
      document.getElementById('error-msg').textContent = errorData['detail'][0]['msg'] || 'Invalid input. Please check your data.';
      return;
    }
    if (response.status === 500){
      const errorData = await response.json();
      console.error("❌ Error Data", errorData);
      document.getElementById('error-msg').textContent = "Internal server error. Please try again later.";
      return;
    }

    const token = await response.json();

    if (token) {
      localStorage.setItem('isLoggedIn', 'true');
      localStorage.setItem('token', token['access_token']);
      window.location.href = '/chat';
    }
  } catch (error) {
    console.error("❌ Error Signin:", error);
    document.getElementById('error-msg').textContent = 'There was an error processing your request. Please try again later.';
  }
}