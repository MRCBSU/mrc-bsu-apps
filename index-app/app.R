library(shiny)
library(bslib)

thematic::thematic_on()
imageToggle <- '<script type="text/javascript">
  const toggler = document.getElementsByTagName("button");
  const navImage = document.querySelector("#navImage");
  })
  </script>
  '

apps <- jsonlite::read_json("apps.json")

app_links <- function(panel) {
  div(style = "display: flex; flex-direction: column; margin:0 12.5%", lapply(apps[[panel]], function(app) {
    link <- a(app$name, href = app$url)
    if (!is.null(app$description) && nzchar(app$description)) {
      tagList(
        link,
        tags$small(class = "text-muted", style = "margin-bottom: 10px;", app$description)
      )
    } else {
      link
    }
  }))
}

ui <- page_navbar(
  title = "MRC BSU Shiny Apps Index",
  tags$head(tags$style("a {
        margin-bottom: 5px;
      }")),
  theme = bs_theme(version = 5, bootswatch = "minty"),
  nav_item(
    a(
      href = "https://www.mrc-bsu.cam.ac.uk/",
      class = "navImageLink",
      style = "text-decoration: none;",
      img(
        id = "navImage",
        src = "images/mrc_bsu_white_text_rgb_80px_c_002.png",
        type = "image/png",
        width = "150px"
      )
    )
  ),
  nav_panel(
    title = "MRC BSU Applications",
    img(
      id = "headerImage",
      src = "images/bsu_cam_logo_ukri.png",
      width = "50%",
      style = "align-self:center;"
    ),
    h3(
      "Below is an index of Shiny applications developed by researchers at the MRC BSU at Cambridge University.",
      align = "center",
    ),
    HTML(
      '<p style="font-size:12px; width:75%; align-self:center;">If you encounter any problems with any of the apps, please contact <a href="mailto:bsu.software@mrc-bsu.cam.ac.uk">bsu.software@mrc-bsu.cam.ac.uk</a> provide a thorough description of the issue, the application you are having issues with, your name, the date and time of the issue, and we will correct it as soon as we are able to.</p>'
    ),
    app_links("panel1")
  ),
  nav_panel(
    title = "Covid-19 Support",
    img(
      id = "header_image",
      src = "images/bsu_cam_logo_ukri.png",
      width = "50%",
      style = "align-self:center;"
    ),
    h3("BSU Support during the Covid-19 Pandemic", align = "center"),
    p(
      'These applications are no longer being actively worked on, but showcase our collective efforts in leveraging predictive analysis to combat the Covid-19 pandemic.',
      style = "font-size:12px; width:75%; align-self:center;"
    ),
    app_links("panel2")
  ),
  nav_spacer(),
  nav_item(
    p(
      icon("copyright"),
      "2024 Cambridge University",
      align = "center",
      style = "font-size: 10px; margin:auto;"
    )
  ),
  
)

server <- function(input, output) {
  
}

shinyApp(ui = ui, server = server)