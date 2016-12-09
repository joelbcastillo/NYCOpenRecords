$(function() {
    // ADD ACTIVE USER
    $("#add-button").click(function() {
        var id = $("#users").val();
        var isAgencyAdmin = $("input[name='is-admin']").is(':checked');
        $.ajax({
            url: "/user/" + id,
            type: "PATCH",
            data: {
                is_agency_active: true,
                is_agency_admin: isAgencyAdmin
            },
            success: function() {
                location.reload();
            }
        })
    });
    // EDIT ACTIVE USER
    $("input[name^='user-status']").click(function() {
        var row = $(this).parents(".row");
        var id = row.find("input[name='user-id']").val();
        var isAgencyAdmin = row.find("input[name^='user-status']:checked").val();
        $.ajax({
            url: "/user/" + id,
            type: "PATCH",
            data: {
                is_agency_admin: isAgencyAdmin
            }
        });
    });
    // REMOVE FROM ACTIVE USERS
    $("#remove").click(function() {
        var idsToRemove = $("input[name^='remove']:checked").parents(".row").find("input[name='user-id']");
        idsToRemove.each(function() {
            $.ajax({  // TODO: it would be better if this called a bulk-op endpoint 'users' *once*
                url: "/user/" + $(this).val(),
                type: "PATCH",
                data: {
                    is_agency_active: false,
                    is_agency_admin: false
                },
                success: function() {
                    location.reload();
                }
            })
        });
    });
});
