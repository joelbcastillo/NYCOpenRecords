/**
 * Created by atan on 10/1/16.
 */

$(document).ready(function () {
    tinymce.init({
        selector: 'textarea',
        height: 200,
    });

    //Call ajax to populate email field with content after textarea is finished loading.
    window.onload=function(){
        $.ajax({
            url: "/responses/email",
            type: 'POST',
            processData: false,
            contentType: false,
            success: function (data) {
                //Data should be html template page.
                tinyMCE.get('email-content').setContent(data);
            },
            error: function (data) {
                alert('fail.');
            }
        });
        $('.prev-slider,.next-slider').click(function () {
            $("#email-summary").html(tinyMCE.get('email-content').getContent());
        });
    };

    $('.carousel').carousel({
        interval: false,
        wrap: false
    });

    $('.title-field').attr('data-parsley-required','');


    $('.next-slider').click(function(e){
        $('#fileupload').parsley().validate();
        if (!($( '#fileupload' ).parsley().isValid())){
            e.preventDefault();
            e.stopPropagation();
        };

    });

    $('#fileupload').submit(function () {
        if ($(".add_to_email").checked) {
            $('.dont_add_to_email').disabled = true;
        }
    });

    // javascript to remove next and prev buttons if at beginning or end of carousel.
    $('#prev-slider').hide();
    $('.carousel').on('slid.bs.carousel', '', function() {
        if ($('.carousel-inner .item:last').hasClass('active')) {
            $('#next-slider').hide();
        }
        else{
            $('#next-slider').show();
        }
        if ($('.carousel-inner .item:first').hasClass('active')) {
            $('#prev-slider').hide();
        }
        else{
            $('#prev-slider').show();
        }
    });
});