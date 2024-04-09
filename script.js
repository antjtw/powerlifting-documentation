document.addEventListener('DOMContentLoaded', function () {
    const contentLinks = document.querySelectorAll('.contents-list-link');
    // Selects all elements with the class 'contents-list-link'.
  
    contentLinks.forEach(link => {
      link.addEventListener('click', smoothScroll);
      // Adds a click event listener to each element with the class 'contents-list-link'.
    });
  
    function smoothScroll(e) {
      e.preventDefault();
      
      const targetId = this.getAttribute('href').substring(1);
      const targetElement = document.getElementById(targetId);
  
      window.scrollTo({
        top: targetElement.offsetTop,
        behavior: 'smooth'
      });
    }
  });